# Model Selection Report (measured results)

**Data source: REAL public civic open data — Chicago 311 + NYC 311.** No synthetic
problems, no auto-generated labels, no fabricated metrics.

- Corpus: `backend/data/real/` — **94,422 distinct real service requests**
  (Chicago 46,649 + NYC 47,773), ingested from the cities' public Socrata APIs.
  Full provenance (endpoints, date window `2026-07-06 → 2026-10-04`, exclusions,
  licenses): `backend/data/real/provenance.md`.
- Labels: **human-entered only**, through the admin **Data & Labels** UI into the
  `real_pairs` / `real_relevance` tables. There is no code path that invents a label.
  (The old synthetic `build_dataset.py`, its CSVs, the rule-derived evaluation
  labels, and all synthetic artifacts have been removed.)

Split policy (no leakage):
- Duplicate pairs: 70/15/15 assigned **at the (source, category, street) bucket
  level** — every bucket goes to exactly one split; a pair is only used when both
  of its buckets are in the same split, so a real request never appears in two splits.
- Team matching: 70/15/15 grouped **by problem** — all team rows of a problem stay
  in one split.

## 1. Clustering (K-Means vs DBSCAN) — MEASURED on real embeddings

Run by `scripts/cluster_compare.py` on a **stratified 15,000-request sample** of the
real corpus (MiniLM-L6-v2, 384-d). Metrics: silhouette (unsupervised, drives the
k / eps choice) and ARI against the **city's own category field** (real metadata, not
fabricated; note the category string also appears in the rendered text, so this
measures how well clustering recovers the city's classification).

| method | params | silhouette | ARI vs city category | noise |
|---|---|---|---|---|
| K-Means | **k=12** | **0.2788** | **0.5406** | 0 |
| DBSCAN | eps=0.351, min_samples=5 | 0.5513 (non-noise) | 0.3060 | 30.9% |

Full search grids (k=2..12; eps=0.205..0.351) are in `backend/artifacts/cluster_config.json`.

Selection rule (documented): higher ARI vs the real city-category labels.
**Decision: KMEANS, k=12** (ARI 0.5406). DBSCAN produces compact clusters (high
silhouette on its non-noise core) but marks ~31–70% of the dense semantic space as
noise and recovers far less of the city's category structure.

## 2. Duplicate detection (supervised classifier) — PENDING human labels

Status: **not yet trained.** The app currently serves the clearly-labelled
**cosine-threshold fallback** (`dedup_method: cosine fallback` in the admin UI).

This is intentional and matches the project rule: *never invent labels*. A supervised
duplicate classifier requires human-labelled duplicate pairs on real requests.

- Candidate pairs have been **mined** from the real corpus (never auto-labelled):
  100 city-flagged (Chicago `duplicate=true`), 100 same-category+same-address repeats,
  100 same-category-different-address negatives — all pending in the review queue.
- **Minimum to train: `MIN_LABELS_DEDUP = 150` labelled pairs** (`app/config.py`).
- Once a human labels ≥150 pairs, `python -m scripts.train_dedup` (or the
  **Train models now** button) trains a HistGradientBoosting grid + logistic baseline
  on the same 7 fit-free features used at serving time, chooses by **validation
  ROC-AUC**, sets the threshold from the **validation** precision-recall curve, and
  reports **held-out test** Precision / Recall / F1 / ROC-AUC / confusion matrix.
  It **refuses** to run below the minimum or if a class is missing — no thin-data
  training, no fake metrics.
- Artifact when trained: `backend/artifacts/dedup_model.joblib` + `dedup_metrics.json`.

**Decision (current): keep the cosine-threshold rule until enough real human labels
exist; then switch to the supervised classifier if it wins on held-out test metrics.**

## 3. Team matching (supervised ranker) — PENDING human labels

Status: **not yet trained.** The app currently serves the documented
**weighted-formula fallback** (`0.55*cos + 0.30*coverage + 0.15*exp`,
weights in `app/config.py`).

- The old category→team rule mapping has been **removed as a label source**.
  Relevance rows are now human-labelled (problem × team grid) on real requests.
- **Minimum to train: `MIN_LABELS_RELEVANCE = 100` labelled rows** (`app/config.py`).
- Once enough rows exist, `python -m scripts.train_ranker` trains a
  logistic-regression vs HistGradientBoosting ranker on the same 6 serving-time
  features, chooses by **validation AUC**, and reports **held-out test** AUC plus
  **Precision@K / Recall@K** computed per problem (on problems whose full team set is
  labelled). It **refuses** below the minimum.
- Recommendations stay explainable: every team gets matched keywords, coverage,
  experience bonus and semantic similarity alongside any model score.
- Artifact when trained: `backend/artifacts/ranker.joblib` + `ranker_metrics.json`.

**Decision (current): keep the weighted formula until enough real human labels exist;
then switch to the trained ranker if it wins on held-out P@K/R@K.**

## Artifacts

| file | content | status |
|---|---|---|
| `backend/artifacts/cluster_config.json` | chosen clustering method + params + search grids | **measured on real data** |
| `backend/artifacts/model_report.json` | machine-readable status of every stage | current |
| `backend/artifacts/dedup_model.joblib` / `dedup_metrics.json` | duplicate classifier + held-out metrics | pending labels |
| `backend/artifacts/ranker.joblib` / `ranker_metrics.json` | team ranker + held-out metrics | pending labels |

## Retrain / pipeline

```bash
cd backend
HF_HOME=$HOME/.hf python -m scripts.train_all
```

`train_all` runs, in order: ingest real data → label mining → clustering (always,
real data) → dedup training (gated on labels) → ranker training (gated on labels) →
model report. The gates never fabricate metrics; if labels are insufficient they
report the exact shortfall instead.
