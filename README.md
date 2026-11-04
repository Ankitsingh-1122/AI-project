# CivicAI — AI/ML + NLP Civic Problem Platform

Citizen problem reports → **NLP preprocessing → sentence embeddings → duplicate
detection (supervised ML) → clustering (K-Means/DBSCAN) → explainable student-team
matching (learned ranker)** → FastAPI + React (glassmorphism) UI.

> **Honesty note (read first).** All ML training data is **real public open
> data** — Chicago 311 + NYC 311 service requests (94,422 distinct records;
> provenance, endpoints, exclusions and licenses in
> `backend/data/real/provenance.md`). There are **no synthetic problems and no
> auto-generated labels**: every duplicate/relevance label is entered by a
> human through the admin **Data & Labels** UI. Until enough labels exist, the
> app serves clearly-labelled fallbacks (cosine-threshold dedup, weighted
> formula matching) and the training scripts **refuse to run** — nothing fake
> is ever reported.

---

## What is real

| Item | Status |
|---|---|
| Training corpus | **Real** — 94,422 Chicago/NYC 311 records (public open data, `backend/data/real/`) |
| NLP (tokenise, stem, TF-IDF, stop-words, Porter) | **Real** (deterministic text processing) |
| Sentence embeddings (`all-MiniLM-L6-v2`) | **Real** pretrained model (CPU) |
| Clustering (K-Means vs DBSCAN, measured selection) | **Real** — measured on a 15k-sample of the real corpus (K-Means k=12, ARI 0.5406 vs city categories) |
| Duplicate labels | **Human-entered** (admin Data & Labels UI → `real_pairs` table); mining only *proposes* candidates |
| Relevance labels | **Human-entered** (admin Data & Labels UI → `real_relevance` table); the old category→team rule is gone as a label source |
| Dedup classifier / team ranker | **Pending human labels** — train with `scripts.train_dedup` / `scripts.train_ranker` (or the "Train models now" button) once the minima are met; until then clearly-labelled fallbacks are served |
| Live app predictions (dedup verdict, teams, clusters) | **Real** — the active model/fallback predicts on new input |

---

## Quick start

> Two ways to run it. **Option A** is the simplest (one port). **Option B** is
> for frontend development (Vite hot-reload). In BOTH options the Python backend
> on port 8000 is required — if you see `ECONNREFUSED` / "Internal Server Error"
> in the Vite terminal, the backend is not running.

### Backend dependencies (both options, once)

```bash
cd backend
python -m venv .venv
# activate:  Windows → .venv\Scripts\activate        macOS/Linux → source .venv/bin/activate
# CPU torch first (small wheel, no CUDA needed):
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

### Option A — single port (production style, recommended)

```bash
cd frontend && npm install && npm run build && cd ../backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`. The uvicorn server serves BOTH the API and the
built SPA. On first start it creates `civic.db`, seeds the demo accounts, and
downloads the MiniLM embedding model (~90 MB, cached afterwards).

### Option B — dev mode (Vite hot-reload + backend)

Terminal 1 (backend):

```bash
cd backend   # venv activated, deps installed
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Terminal 2 (frontend):

```bash
cd frontend
npm install
npm run dev    # http://localhost:5173 — proxies /api/* to localhost:8000
```

Both processes must stay running; Vite returns 500 ("Internal Server Error")
for every API call while the backend is down.

No environment variables are required (`EMBEDDER` defaults to `sentence`;
`HF_HOME` only changes where the embedding model cache lives).

### Demo logins

| Role | Email | Password |
|---|---|---|
| Admin | `admin@civic.demo` | `admin123` |
| Citizen | `citizen1@civic.demo` / `citizen2@civic.demo` | `demo123` |
| Teams | `team1@civic.demo` … `team8@civic.demo` | `demo123` |

---

## The AI/ML pipeline

When a problem is stored (`POST /api/problems`), `app/pipeline.py` runs:

1. **Preprocess** (`app/ml/preprocess.py`) — clean, tokenize, stop-word removal,
   Porter stemming. For the semantic embedder only light cleaning is applied
   (stemmed/stop-removed text degrades sentence embeddings).
2. **Embed** (`app/ml/embed.py`) — **SentenceTransformer** `all-MiniLM-L6-v2`
   (primary) with a **TF-IDF fallback** if the model can't load.
3. **Similarity search** — cosine similarity vs. all stored problems
   (`app/ml/dedup.py`).
4. **Duplicate verdict** — if a trained classifier artifact exists (trained on
   human-labelled real pairs, 7 fit-free features: semantic cos/distance, Porter
   uni/bigram Jaccard, length ratio/delta, same-category; threshold chosen on a
   **validation** split) it decides with `P(duplicate) ≥ threshold`. Until enough
   human labels exist, the active method is the **cosine-threshold rule** — and
   the UI reports which method is in use (`dedup.method` in every API response).
5. **Clustering** — method + params from `artifacts/cluster_config.json`
   (K-Means vs DBSCAN measured on the REAL corpus; currently K-Means k=12,
   ARI 0.5406 vs the city's own category field). DBSCAN noise becomes an
   "Unassigned" cluster.
6. **Team matching** — each (problem, team) is scored with the active ranker:
   the learned ranker (6 features: semantic cosine, Porter uni/bigram Jaccard,
   skill Jaccard, keyword coverage, experience bonus) when trained on human
   labels, otherwise the documented weighted formula
   `0.55·cos + 0.30·coverage + 0.15·exp`. Top-K returned with a
   **human-readable explanation** (matched keywords, score breakdown, reason).

The admin dashboard ("Trained models in service") always shows exactly which
mode (trained model vs fallback) is active.

---

## Training data (real + human-labelled)

- **Corpus** — `backend/data/real/` holds **94,422 distinct real Chicago/NYC 311
  service requests** (public open data, window 2026-07-06 → 2026-10-04). Each
  row is one real request (unique SR number / NYC unique_key). Text is rendered
  from the request's real field values (type + street + city + zip). Full
  endpoints, exclusions and licenses: `backend/data/real/provenance.md`.
  Ingest: `python -m scripts.ingest_real` (date-windowed, deduped by unique key).
- **Labels** — there is **no auto-generated label anywhere**.
  - *Duplicate pairs*: `python -m scripts.label_mining` **proposes** candidate
    pairs from the real corpus (city-flagged duplicates, same-address repeats,
    same-type-different-street negatives). They enter the admin **Data & Labels**
    queue **pending**; a human marks each duplicate / not.
  - *Relevance*: the same script samples real problems × the app's student teams
    into a grid; a human marks each (problem, team) relevant / not.
  - Every label is stored with `labeled_by` / `labeled_at` (which user, when).
- **Gates** — `scripts.train_dedup` and `scripts.train_ranker` **refuse to run**
  below `MIN_LABELS_DEDUP` (150 pairs) / `MIN_LABELS_RELEVANCE` (100 rows) in
  `app/config.py`, and refuse if a class is missing. No thin-data training, no
  invented metrics.

---

## NLP techniques

- **Preprocessing:** regex clean, Unicode-normalise, tokenize, stop-word list,
  **Porter stemming** (nltk) for lexical features.
- **TF-IDF baseline:** `TfidfVectorizer` (fitted per corpus), cosine similarity.
- **Semantic embeddings:** `sentence-transformers/all-MiniLM-L6-v2` (384-dim,
  CPU). Embeddings are disk-cached by corpus hash (`data/cache/`).

---

## Algorithms, model selection & measured metrics

**Selection is by measured performance, never hardcoded.** Every number below is
measured on real data with a documented split policy; the machine-readable
report is `docs/MODEL_SELECTION.md` + `backend/artifacts/model_report.json`.

### 1. Clustering — K-Means vs DBSCAN (MEASURED on real data)
`scripts.cluster_compare.py` on a stratified 15,000-request sample of the real
corpus (MiniLM embeddings). K-Means k=2..12 by silhouette; DBSCAN eps from
median k-distance (k=5) grid, min_samples=5. Chosen by **higher ARI vs the
city's own category field** (real metadata labels; silhouette is the
unsupervised k/eps selector).

| method | params | silhouette | ARI vs city category | noise |
|---|---|---|---|---|
| **K-Means (selected)** | **k=12** | 0.2788 | **0.5406** | 0 |
| DBSCAN | eps=0.351, ms=5 | 0.5513 (non-noise) | 0.3060 | 30.9% |

**Decision: K-Means k=12** (stored in `artifacts/cluster_config.json`, used by
the live app). DBSCAN makes compact clusters but marks ~31–70% of the dense
semantic space as noise and recovers far less of the city's category structure.

### 2. Duplicate detection — supervised classifier (PENDING human labels)
**Not yet trained — no labels exist yet, and we do not invent labels.** Active
method: **cosine-threshold rule** (clearly reported as the fallback in the UI).

Once a human labels ≥ `MIN_LABELS_DEDUP` (150) pairs in the admin Data & Labels
queue: 7 pair features → {LogisticRegression, HistGradientBoosting grid},
selected by **validation ROC-AUC**; threshold from the **validation**
precision–recall curve; **70/15/15 assigned at (source, category, street)
bucket level** so a real request never appears in two splits; final metrics
reported on **test only** (P/R/F1/ROC-AUC + confusion). The script **refuses**
below the minimum or if a class is missing.

### 3. Team matching — learned ranker (PENDING human labels)
**Not yet trained** — active method: documented weighted formula
`0.55·cos + 0.30·coverage + 0.15·exp`. The old category→team rule mapping is
**gone as a label source**; relevance is human-labelled (problem × team grid).

Once ≥ `MIN_LABELS_RELEVANCE` (100) rows are labelled: 6 features →
{LogisticRegression, HGB} selected by **validation AUC**; **70/15/15 grouped by
problem** (all team rows of a problem in one split); held-out **test** AUC +
**P@K / R@K** per problem (complete problems only) reported. Refuses below the
minimum.

---

## Production: saved models & retraining

Artifacts written to `backend/artifacts/` and loaded lazily by
`app/ml/model_store.py` (a broken/absent artifact degrades gracefully to the
cosine/formula fallback):

| file | content |
|---|---|
| `dedup_model.joblib` | classifier + threshold + features + categories + test metrics |
| `ranker.joblib` | team ranker (+ scaler) + features |
| `cluster_config.json` | chosen clustering method + parameters |
| `*_metrics.json` | measured metrics per component |

**Run the full real-data pipeline (one command):**

```bash
cd backend
python -m scripts.train_all
```

This runs, in order: ingest real 311 data → candidate-pair/relevance mining →
clustering on real embeddings (always) → dedup training (**gated** on human
labels) → ranker training (**gated**) → model report. The gated stages refuse
below the config minima instead of training on thin data.

Individual stages (each is a standalone, importable script):

```bash
python -m scripts.ingest_real      # pull real Chicago/NYC 311 -> data/real/
python -m scripts.label_mining     # upsert corpus + propose candidate label queues
python -m scripts.cluster_compare  # K-Means vs DBSCAN on real embeddings
python -m scripts.train_dedup      # duplicate classifier (refuses < MIN_LABELS_DEDUP)
python -m scripts.train_ranker     # team-matching ranker (refuses < MIN_LABELS_RELEVANCE)
```

Or, without a terminal: admin dashboard → **Data & Labels** → *Mine more
candidates* and **▶ Train models now** (the button calls the same gated
training and reports the exact shortfall if the minima aren't met).

---

## Configuration (env vars)

| var | default | meaning |
|---|---|---|
| `EMBEDDER` | `sentence` | `sentence` (all-MiniLM) or `tfidf` (baseline) |
| `DATABASE_URL` | `sqlite:///./civic.db` | any SQLAlchemy URL (Supabase/Postgres) |
| `DEDUP_THRESHOLD` | `0.75` | cosine fallback threshold (classifier threshold comes from the artifact) |
| `MIN_LABELS_DEDUP` | `150` | labelled pairs required before the dedup classifier will train |
| `MIN_LABELS_RELEVANCE` | `100` | labelled relevance rows required before the ranker will train |
| `SEED_ON_START` | `true` | seed demo users/teams/problems into an empty DB |
| `CIVIC_NO_MODELS` | — | set to `1` to force fallback (no trained artifacts) |
| `JWT_SECRET` | dev value | change in production |
| `SUPABASE_URL` / `SUPABASE_PUBLISHABLE_KEY` | — | real-user auth (validate Supabase tokens, map to local accounts) |

---

## Running the tests

```bash
cd backend
HF_HOME=$HOME/.hf EMBEDDER=sentence python -m pytest -q
```

36 tests: API (auth, problems, teams, feedback, admin), ML unit tests
(preprocessing, TF-IDF, threshold tuning, clustering incl. config dispatch,
ranker feature parity, artifact loaders, classifier decision ordering).

---

## API (SRS §10, mounted under `/api`)

Auth: `POST /api/auth/login` for demo accounts (local JWT; Bearer, cookie or
`X-Civic-Token` all accepted). **Real users** sign in through Supabase Auth in
the browser; the backend validates the Supabase token (`/auth/v1/user`) and maps
it to a local account (created on first login). Key routes:

- `POST /api/problems` — submit; returns full analysis (duplicate verdict,
  similar, cluster, recommended teams).
- `GET /api/problems/{id}` · `GET /api/ai/analysis/{id}` — full NLP/ML
  transparency (tokens, keywords, threshold, duplicate **method + probability**,
  per-team score breakdown incl. model vs formula score).
- `POST /api/ai/check-duplicate` — duplicate check (**method** + **probability**).
- `GET /api/ai/clusters` · `GET /api/ai/recommend-teams/{id}`.
- `GET /api/admin/statistics` · `GET /api/admin/model-performance`
  (adds a **`trained_models`** section: what is active, params, held-out test
  metrics; plus a **`labeling`** section: real labelling progress + provenance).
- **Human labelling (admin)** — `GET /api/labels/status`,
  `GET|POST /api/labels/pairs` (review + label candidate duplicate pairs),
  `GET|POST /api/labels/relevance` (label problem × team rows),
  `POST /api/labels/mine` (propose more candidates), `POST /api/labels/retrain`
  (train gated on the label minima).
- `GET /api/stats/summary`, `/api/teams/*`, `/api/feedback`, `/api/auth/*`.

---

## Project layout

```
civic-platform/
├─ backend/
│  ├─ app/
│  │  ├─ main.py, deps.py, models.py, pipeline.py, config.py, seed.py
│  │  ├─ ml/
│  │  │  ├─ preprocess.py   # clean/tokenize/stem/TF-IDF
│  │  │  ├─ embed.py        # SentenceTransformer + TF-IDF fallback
│  │  │  ├─ dedup.py        # similarity + trained-classifier decisions
│  │  │  ├─ cluster.py      # config-driven K-Means/DBSCAN
│  │  │  ├─ matching.py     # learned ranker + explainable breakdown
│  │  │  ├─ evaluate.py     # label-driven P/R/F1, P@K/R@K, purity, trained_models
│  │  │  └─ model_store.py  # lazy artifact loader + graceful fallback
│  │  └─ routers/           # auth, problems, teams, feedback, ai, admin, labels
│  ├─ scripts/              # real-data pipeline (ingest_real, label_mining,
│  │                         #   cluster_compare, train_dedup, train_ranker, train_all)
│  ├─ data/real/            # REAL Chicago/NYC 311 corpus + provenance.md
│  ├─ artifacts/            # trained models + cluster config (loaded by the app)
│  └─ tests/                # pytest suite
├─ frontend/                # React + Vite + Recharts (glassmorphism, dual theme)
└─ docs/                    # MODEL_SELECTION.md (measured results + pending stages)
```

---

## Deployment notes

- CPU-only; `torch` (CPU wheel) + `sentence-transformers`. First request loads
  the model (~a few seconds) — subsequent requests are fast.
- For Supabase/Postgres set `DATABASE_URL` and `SEED_ON_START=false` if data
  already exists.
- Bind `0.0.0.0` when behind a proxy; the SPA uses same-origin relative `/api`.
