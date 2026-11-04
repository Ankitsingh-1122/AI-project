"""Full REAL-data ML pipeline, in order:

  1. scripts.ingest_real      (real Chicago/NYC 311 -> data/real/corpus_*.csv)
  2. scripts.label_mining     (corpus -> real_problems + candidate label queues)
  3. scripts.cluster_compare  (K-Means vs DBSCAN on real embeddings -> config)
  4. scripts.train_dedup      (human-labelled pairs -> classifier; GATED)
  5. scripts.train_ranker     (human-labelled rows -> ranker; GATED)
  6. artifacts/model_report.json (what is trained, from what data, how)

Gates: steps 4-5 REFUSE below app/config.py MIN_LABELS_DEDUP / MIN_LABELS_RELEVANCE
human labels — no training on thin data, no fake metrics. Until enough labels
exist the app serves the honest fallbacks (cosine-threshold dedup, weighted
formula matching) and reports that state in the admin UI.

Nothing in this pipeline invents data or labels: data provenance is
data/real/provenance.md, labels are human-entered (admin Data & Labels UI).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
ART = os.path.join(BACKEND, "artifacts")


def run_stage(name: str, *args: str, check: bool = True) -> bool:
    cmd = [sys.executable, "-m", f"scripts.{name}", *args]
    print(f"\n=== {name} ===")
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=BACKEND)
        ok = r.returncode == 0
    except Exception as e:  # noqa: BLE001
        print(f"FAILED: {e}")
        return False
    print(f"{'OK' if ok else 'FAILED'} {name} in {time.time()-t0:.1f}s")
    if check and not ok:
        raise SystemExit(1)
    return ok


def _artifact(name: str):
    path = os.path.join(ART, name)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def main() -> None:
    os.makedirs(ART, exist_ok=True)
    stages: list[dict] = []

    run_stage("ingest_real", "--days", "90", "--max-rows", "60000", check=False)
    stages.append({"stage": "ingest", "status": "ok" if _corpus_ok() else "skipped/failed"})
    if not _corpus_ok():
        raise SystemExit("REAL corpus missing — cannot continue (no synthetic fallback)")

    run_stage("label_mining")
    stages.append({"stage": "label_mining", "status": "ok"})
    run_stage("cluster_compare")
    stages.append({"stage": "cluster_compare", "status": "ok"})

    # gated on human labels — refuses itself below the config minima
    run_stage("train_dedup", check=False)
    run_stage("train_ranker", check=False)

    dedup_m = _artifact("dedup_metrics.json")
    ranker_m = _artifact("ranker_metrics.json")
    if dedup_m and ranker_m:
        dedup_status = "trained"
        ranker_status = "trained"
    else:
        dedup_status = ranker_status = "pending_human_labels"

    report = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "data": "REAL Chicago + NYC 311 service requests (public open data) — "
                "see data/real/provenance.md for endpoints, date window, exclusions",
        "labels": "human-entered via the admin Data & Labels UI (real_pairs / "
                  "real_relevance tables); no automatic or rule-generated labels",
        "stages": stages,
        "dedup": {"status": dedup_status, **({} if not dedup_m else dedup_m)},
        "ranker": {"status": ranker_status, **({} if not ranker_m else ranker_m)},
        "cluster": _artifact("cluster_config.json") or {},
        "fallbacks": (
            "Until enough human labels exist: duplicate detection = cosine-threshold "
            "rule; team matching = weighted formula (both clearly reported in the UI)."
        ),
    }
    with open(os.path.join(ART, "model_report.json"), "w") as f:
        json.dump(report, f, indent=2, default=float)
    print("\nmodel_report.json written:",
          "dedup =", dedup_status, "| ranker =", ranker_status)


def _corpus_ok() -> bool:
    return os.path.exists(os.path.join(BACKEND, "data", "real", "corpus_all.csv"))


if __name__ == "__main__":
    main()
