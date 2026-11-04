"""Cluster-method comparison on REAL Chicago/NYC 311 data.

Corpus: a stratified-by-category seeded sample (default 15,000 of 94,422
ingested real requests; scripts/ingest_real.py + data/real/provenance.md).
Texts are the real rendered request lines (type + street + city + zip).

Both K-Means (k=2..12, silhouette-selected) and DBSCAN (k-distance eps grid,
min_samples=5) are run on MiniLM embeddings. Metrics:
  * Silhouette (primary, unsupervised — used for k / eps selection)
  * ARI vs the city's own category field (real metadata labels, not
    fabricated; caveat: the category string appears in the text, so this
    measures how well clustering recovers the city's own classification)
  * DBSCAN noise fraction; cluster-size distribution

No synthetic data, no ARI against invented labels. Output:
artifacts/cluster_config.json (consumed by app/ml/cluster.py — schema
unchanged).
"""
from __future__ import annotations

import argparse
import json
import os
import time

import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN, KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score

from .nlp_common import save_json, st

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.normpath(os.path.join(HERE, "..", "data", "real", "corpus_all.csv"))
SEED = 20261004


def load_sample(n: int) -> pd.DataFrame:
    df = pd.read_csv(CORPUS, dtype=str).fillna("")
    if n and n < len(df):
        # stratified by category: proportional shares, >=1 per category
        shares = (df["category"].value_counts(normalize=True) * n).round(0)
        shares = shares.clip(lower=1)
        while shares.sum() > n:  # trim the largest
            shares.loc[shares.idxmax()] -= 1
        parts = []
        for cat, k in shares.items():
            parts.append(df[df["category"] == cat].sample(int(k), random_state=SEED))
        df = pd.concat(parts).sample(frac=1.0, random_state=SEED)
    return df.reset_index(drop=True)


def run(n: int) -> dict:
    t0 = time.time()
    df = load_sample(n)
    texts = df["text"].tolist()
    cats = df["category"].tolist()
    X = st.encode(texts, tag=f"real_cluster_{n}")
    print(f"sample: {len(df)} real requests, {len(set(cats))} categories")

    SIL_SAMPLE = 5000
    kmeans_res = {}
    best_km = None
    for k in range(2, 13):
        km = KMeans(n_clusters=k, n_init=10, random_state=SEED).fit(X)
        labels = km.labels_
        sil = float(silhouette_score(X, labels, sample_size=min(SIL_SAMPLE, len(df)),
                                     random_state=SEED))
        ari = float(adjusted_rand_score(cats, labels))
        kmeans_res[str(k)] = {"silhouette": round(sil, 4), "ari": round(ari, 4)}
        print(f"  kmeans k={k:2d}  sil={sil:.4f}  ari={ari:.4f}")
        if best_km is None or sil > best_km["sil"]:
            best_km = {"k": k, "sil": sil, "ari": ari, "labels": labels}

    # DBSCAN: k-distance (k=5) anchor + grid
    from sklearn.neighbors import NearestNeighbors
    kk = NearestNeighbors(n_neighbors=5).fit(X)
    eps_kd = float(np.sort(kk.kneighbors(X, return_distance=True)[0])[:, -1].mean())
    grid = sorted({round(eps_kd * m, 3) for m in (0.7, 0.8, 0.9, 1.0, 1.1, 1.2)})
    dbscan_res = {}
    best_db = None
    for eps in grid:
        db = DBSCAN(eps=eps, min_samples=5, n_jobs=-1).fit(X)
        labels = db.labels_
        n_noise = int((labels == -1).sum())
        noise = n_noise / len(labels)
        sil = None
        non_noise = labels[labels != -1]
        if len(set(non_noise)) >= 2 and (len(non_noise) > 0.05 * len(labels)):
            sil = float(silhouette_score(X[labels != -1], non_noise,
                                         sample_size=min(SIL_SAMPLE, len(non_noise)),
                                         random_state=SEED))
        ari = float(adjusted_rand_score(cats, labels))
        dbscan_res[str(eps)] = {"silhouette": round(sil, 4) if sil is not None else None,
                                "ari": round(ari, 4), "noise": round(noise, 4)}
        print(f"  dbscan eps={eps:.3f}  sil={sil if sil is None else round(sil,4)}  "
              f"ari={ari:.4f}  noise={noise:.1%}")
        if sil is not None and (best_db is None or sil > best_db["sil"]):
            best_db = {"eps": eps, "sil": sil, "ari": ari, "noise": noise, "labels": labels}

    # selection: highest ARI (real city-category labels); silhouette is the
    # unsupervised tiebreaker within a method
    km_pick = {"method": "kmeans", "score": best_km["ari"], "tie": best_km["sil"],
               "payload": {"k": best_km["k"], "silhouette": round(best_km["sil"], 4),
                           "ari": round(best_km["ari"], 4), "n_clusters": best_km["k"]}}
    db_pick = ({"method": "dbscan", "score": best_db["ari"], "tie": best_db["sil"],
                "payload": {"eps": best_db["eps"],
                            "silhouette": round(best_db["sil"], 4),
                            "ari": round(best_db["ari"], 4),
                            "noise_ratio": round(best_db["noise"], 4),
                            "n_clusters": len(set(best_db["labels"])) - 1}}
               if best_db else None)
    selected = (km_pick if (db_pick is None or km_pick["score"] > db_pick["score"])
                else db_pick)

    # size distribution of the selected method
    labels = best_km["labels"] if selected["method"] == "kmeans" else best_db["labels"]
    sizes = pd.Series(labels).value_counts().sort_values(ascending=False)
    res = {
        "selected": selected["method"],
        "kmeans": {"k": best_km["k"], "silhouette": round(best_km["sil"], 4),
                   "ari": round(best_km["ari"], 4), "search": kmeans_res},
        "dbscan": ({"eps": best_db["eps"], "silhouette": round(best_db["sil"], 4),
                    "ari": round(best_db["ari"], 4), "noise_ratio": round(best_db["noise"], 4),
                    "search": dbscan_res, "k_distance_eps": round(eps_kd, 4)}
                   if best_db else {"error": "no eps in grid yielded usable clusters",
                                    "k_distance_eps": round(eps_kd, 4)}),
        "cluster_sizes_top": {str(int(kk_)): int(v) for kk_, v in sizes.head(12).items()},
        "dataset": f"REAL Chicago/NYC 311 stratified sample: {len(df)} of 94,422 ingested "
                   f"requests, {len(set(cats))} categories (seed {SEED}) — "
                   f"see data/real/provenance.md",
        "labels": "city-provided category field (real metadata); silhouette is the "
                  "unsupervised selection metric; no fabricated labels",
        "train_seconds": round(time.time() - t0, 1),
    }
    save_json("cluster_config.json", res)
    print(f"selected: {selected['method']} "
          f"(k={res['kmeans']['k']} / eps={res['dbscan'].get('eps')}) "
          f"in {res['train_seconds']}s")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=15000)
    run(ap.parse_args().n)
