# CivicAI — Detailed Presentation Guide
### A step-by-step explanation of exactly what the website does, what happens in the background, and how to present it to a professor.

> **How to use this document.** Read Parts 1–4 first so you can explain the big picture in one breath.
> Then study Part 5 (the background flow) and Part 14 (expected questions) — those are what a
> professor will probe. Rehearse Part 13 (the live demo) once before you present.
> Every number in this guide is **measured from the running system / the real dataset**, not invented.

---

## Part 1 — The one-line pitch

> "CivicAI is a web platform where **citizens report civic problems** (pothole, dead street light,
> sewage, garbage), and the system automatically **detects duplicate reports, groups similar problems
> into clusters, and recommends the best student teams to solve them** — with a **human-readable
> explanation for every recommendation**. The machine-learning is trained and evaluated on **real
> public 311 open data (Chicago + New York City)**, and — where real human labels don't yet exist —
> it says so instead of faking a number."

That last clause (honesty) is your strongest point. A professor respects a student who knows exactly
what is real and what is still pending.

---

## Part 2 — The problem it solves (context / motivation)

1. **Duplicate reporting.** When a street light is out, 20 residents each file a report. The city
   wastes effort fixing the same thing 20 times. The platform **folds duplicates into one incident**.
2. **Matching effort to skill.** A pothole needs a surveying/civil team; a water-quality problem needs
   a different team. Manually assigning reports to teams doesn't scale. The platform **ranks every team
   for each problem and explains why**.
3. **No visibility.** Citizens have no way to see that their problem is already being handled, or which
   team owns it. The platform gives citizens a **live status** and teams a **work queue**.

Real-world grounding: this mirrors actual 311 systems, which process **millions of structured service
requests per year** in large cities. Our ML is trained on a slice of exactly that kind of data.

---

## Part 3 — Architecture at a glance

```
                ┌──────────────────────────────────────────────────────────────┐
                │                         BROWSER (React SPA)                    │
                │  Landing · Login · Submit · Dashboard · Problem detail ·        │
                │  Team home · Team "Recommended" · Admin dashboard               │
                │  Auth state (Supabase session / demo JWT) · dual theme · toasts │
                └───────────────▲──────────────────────────────┬────────────────┘
                                │  JSON over HTTP (same origin) │
                                │  Authorization: Bearer <token>│
                ┌───────────────┴──────────────────────────────▼────────────────┐
                │                    FASTAPI  BACKEND  (Python)                   │
                │                                                                │
                │  routers/  auth · problems · teams · ai · admin · labels ·      │
                │             feedback · notifications                           │
                │                                                                │
                │  pipeline.py  = the analysis engine that runs on every problem  │
                │  ml/          = preprocess · embed · dedup · cluster ·          │
                │                 matching · evaluate · model_store              │
                │                                                                │
                │  On startup: create tables · seed demo data · load saved models│
                └───────────────▲──────────────────────────────┬────────────────┘
                                │                              │
                 ┌──────────────┴─────────┐      ┌─────────────▼──────────────┐
                 │   DATABASE (SQLite)    │      │   SAVED MODEL ARTIFACTS    │
                 │  users, problems, teams,│      │  cluster_config.json       │
                 │  matches, clusters,    │      │  (K-Means k=12, measured)  │
                 │  notifications, msg,   │      │  dedup_model.joblib  (when │
                 │  feedback, real_*      │      │   trained on human labels) │
                 │                         │      │  ranker.joblib       (when│
                 └──────────────▲──────────┘      │   trained)                │
                                │                 └───────────────────────────┘
                 ┌──────────────┴──────────┐
                 │  SUPABASE (real auth)   │  +  REAL 311 corpus:
                 │  signup/login/validate  │     backend/data/real/ (94,422 rows)
                 └─────────────────────────┘
```

Key idea to state out loud: **one process serves both the API and the built frontend on a single
port (8000)**, so there is no CORS/config headache. The ML "brain" is `app/pipeline.py`, which runs
a fixed sequence of steps on every problem that is stored.

---

## Part 4 — Tech stack (say this in one breath)

| Layer | Technology | Why |
|---|---|---|
| Frontend | **React 18 + Vite**, Recharts, React Router | Fast, modern SPA; charts for the admin |
| Styling | Hand-written CSS, **glassmorphism**, light/dark themes | Clean, no heavy UI framework |
| Backend / API | **FastAPI (Python)**, Pydantic | Auto OpenAPI docs, typed, async |
| Database | **SQLite** (runs instantly); swappable to **Supabase/Postgres** via one env var | Zero-setup demo, real deployment path |
| Auth | **Supabase Auth** for real users + **local JWT** for demo accounts | Real product-style auth, works offline |
| NLP / ML | **scikit-learn**, **sentence-transformers**, **NumPy**, **nltk** | Industry-standard, reproducible |
| Embedding model | **all-MiniLM-L6-v2** (384-dim, CPU) | Small, fast, good semantics on CPU |
| Charts (admin) | **matplotlib + seaborn** rendered server-side to PNG | No chart-library fragility in the browser |
| Packaging | Single-port uvicorn serves API **and** built SPA | One command to run everything |

---

## Part 5 — What happens in the background (THE core section)

This is what the professor will want to understand. There are four "background moments."

### 5.1 When the app first starts (server boot)
1. FastAPI starts on port 8000.
2. SQLAlchemy **creates any missing tables** in `civic.db` if they don't exist.
3. If the DB is empty and `SEED_ON_START=true`, it **seeds demo data**: 2 citizens, an admin,
   **8 student teams** (each with real skills, interests, experience, and member names), and
   **33 demo problems** — and it runs the full ML pipeline on each so the dashboard is alive on first open.
4. The embedding model (MiniLM) is **loaded once and kept in memory**; every text embedding after
   that is **disk-cached** by a hash of the corpus, so repeated requests are fast.
5. Saved model artifacts (e.g. the clustering config) are **loaded lazily**; if one is missing or
   broken, the app **degrades gracefully** to a documented fallback instead of crashing.

> **Say this:** "Startup is idempotent — it only seeds an empty database, and every ML model is
> loaded once and cached, so the first request is the only slow one."

### 5.2 When a citizen submits a problem — the full pipeline, step by step

This is the heart of the system. `app/pipeline.py → analyze_problem()` runs these steps **on every
new problem**:

1. **Persist the problem** to the `problems` table (title, description, location, category, owner).
2. **Preprocess the text** (`app/ml/preprocess.py`):
   - Light cleaning for the semantic embedder (keep words natural — stemming/stop-word removal
     would *hurt* sentence embeddings),
   - but also a fully **stemmed + stop-word-removed token list** for the lexical features
     (Porter stemmer via nltk) and for the "top keywords" the UI shows.
3. **Embed** the problem (`app/ml/embed.py`) into a **384-dimensional vector** using
   `all-MiniLM-L6-v2`. This vector is the problem's "semantic meaning" — two problems about the same
   kind of thing end up with vectors that point in similar directions.
   - *Fallback:* if the sentence model can't load, it automatically uses **TF-IDF vectors** instead.
4. **Similarity search** (`app/ml/dedup.py`): compute **cosine similarity** between the new problem's
   vector and the vectors of **every stored problem**; keep the top matches (≥ 0.30) as "similar problems."
5. **Duplicate verdict** — two possible methods (the app reports *which one* was used):
   - **Trained classifier** (active only once a human has labelled ≥150 real duplicate pairs):
     a supervised model scores a **7-feature vector** (semantic cosine, L2 distance, Porter
     unigram Jaccard, Porter bigram Jaccard, length ratio, length delta, same-category).
     If `P(duplicate) ≥ threshold` → it's a duplicate. The threshold was chosen on a **validation**
     split, not the test split (no leakage).
   - **Cosine-threshold fallback** (the default today, until human labels exist):
     if cosine similarity ≥ the configured threshold (0.75) → duplicate.
   - The UI shows **method + probability/score**, so it's transparent, not a black box.
6. **Clustering** (`app/ml/cluster.py`): the problem is assigned to a cluster using the
   **measured best configuration** in `cluster_config.json`. Currently that is **K-Means with k=12**
   (chosen by measured Adjusted-Rand-Index vs the city's own category labels on the real corpus).
   If the chosen method were DBSCAN, any "noise" points would form an "Unassigned" cluster.
7. **Team matching** (`app/ml/matching.py`): for **each of the 8 teams**, compute a relevance score.
   - The score combines **three explainable signals**:
     - **text similarity** — cosine between problem vector and the team's profile vector,
     - **keyword coverage** — what fraction of the problem's key terms appear in the team's
       skills/interests,
     - **experience bonus** — does the team's stated experience match the problem's keywords.
   - With the semantic embedder the production weights are
     **`0.60·text_sim + 0.35·coverage + 0.05·experience`** (from `app/config.py`).
   - Top-K (5) teams are saved as **`matches`** with status `suggested`.
   - **Explainability:** every match stores a human-readable reason, e.g. *"team skills/interests
     overlap problem keywords: street light; covers 80% of the problem's key terms; team profile is
     semantically close (sim 0.62). team: Smart Street Labs."*
8. **Notifications & status**: the owner and relevant teams are notified; the problem appears in the
   team's **"Recommended"** queue and the citizen's dashboard.
9. **Return the full analysis to the browser** — that's why the "problem detail" page can show tokens,
   keywords, the duplicate method + probability, the cluster, and per-team score breakdowns.

> **Say this (the money sentence):** "Every single number you see on the screen — the duplicate
> probability, the cluster, the team score and its reason — is computed live by this pipeline and
> stored, not canned. And the app always tells you *which* method produced it."

### 5.3 When a team reviews the "Recommended" queue
- Team logs in → sees problems ranked for **their** team (skills/interests matched).
- **Accept** → the match is marked `accepted`, the problem's status moves to **assigned to that
  team**, and the citizen is **notified** ("Team X accepted your problem").
- **Reject** → marked `rejected`, removed from the queue.
- **Feedback** (👍 good rec / 👎 bad rec) → stored in `feedback`; this is real signal for improving
  the matcher.
- Near-duplicate logic: once a team decides on a problem, other "suggested" rows for the *same*
  problem (or an identical title) are retired from the Suggested tab so the queue stays clean, but
  remain visible under "All."

### 5.4 When the admin opens the dashboard
- **Statistics** (counts by status/category, duplicates caught, matches, feedback) — computed live
  from the DB.
- **Analytics charts** — **matplotlib/seaborn rendered on the server** as transparent PNGs, themed to
  light/dark, so the browser never has to run a chart engine.
- **AI/ML performance** — live Precision/Recall/F1 + confusion matrix for dedup (on labelled eval
  pairs, if any), Precision@K for matching (on labelled relevance, if any), cluster purity, and a
  **`trained_models`** section that states exactly which method is active (trained vs fallback),
  its parameters and held-out metrics — plus a **`labeling`** section showing how many real labels
  exist and whether enough to train.
- **Data & Labels** — the human-labelling workspace (see Part 7).

---

## Part 6 — The ML algorithms, explained simply

### 6.1 NLP preprocessing
- **Cleaning** (regex/Unicode normalise), **tokenisation**, **stop-word removal**, **Porter
  stemming** (`nltk`) — e.g. "lights", "lighting" → "light". Used for the *lexical* features and the
  displayed keywords. The *semantic* embedder gets lightly-cleaned natural text on purpose.

### 6.2 Embeddings — the "meaning vector"
- **all-MiniLM-L6-v2** is a small (distilled BERT) **Sentence-Transformer**. It maps any short text to
  a **384-number vector** such that *meaning-similar* texts are *geometrically close* (high cosine).
- That's why "street light not working near bus stand" and "street lamp off, very dark" score high
  even though the words differ. It runs **on CPU**, is **pretrained** (not tuned on our data), and is
  **disk-cached** for speed.
- **TF-IDF** is the baseline/fallback: a classic statistical "importance of a word in this document"
  vector. Less semantic, but deterministic and dependency-light.

### 6.3 Duplicate detection
- **Unsupervised core:** cosine similarity between embeddings. A threshold decides "duplicate."
- **Supervised upgrade (when labelled):** a classifier on 7 pair-features learns a better boundary
  than raw cosine (it can weigh, e.g., "same address & same type" more than "similar words"). Selected
  by **validation ROC-AUC**; threshold from the **validation** precision–recall curve. **70/15/15 split
  assigned at the (source, category, street) bucket level** so a real request never appears in two
  splits — a concrete **no-leakage** guarantee.

### 6.4 Clustering
- **K-Means**: partition N points into k clusters by minimizing within-cluster distance. k is searched
  (2–12) and chosen by a **measured** criterion.
- **DBSCAN**: density-based; finds arbitrarily-shaped clusters and flags **noise** (points that don't
  belong to any dense region). We search an eps grid around the median k-distance.
- **How we chose (real data):** on a stratified **15,000-request sample** of the real Chicago/NYC
  corpus, we computed **silhouette** (unsupervised cohesion) and **Adjusted Rand Index vs the city's
  own category field** (real metadata). **K-Means k=12 won (ARI 0.5406)**; DBSCAN made compact
  clusters but marked ~31–70% as noise and recovered far less of the city's category structure. That
  winner is what the app uses.

### 6.5 Team matching (explainable ranking)
- Each (problem, team) pair is scored by the weighted formula (or, once trained, a learned ranker on
  6 features: semantic cosine, Porter uni/bigram Jaccard, skill Jaccard, keyword coverage, experience
  bonus, plus category signals). **Top-K** returned.
- **Explainability is built in:** the score is *decomposed* into its parts (text sim, coverage,
  experience, matched keywords) and a plain-English **reason** is generated. This is what makes it
  defensible to a professor and usable by a real team — it's not "trust the number."

---

## Part 7 — The data story (the honesty part — lead with this if asked "is this real?")

This is the part that most distinguishes the project. Be precise:

**The training corpus is REAL public open data.**
- **94,422 distinct real service requests** ingested from the official **Chicago 311** and
  **New York City 311** open-data APIs (Socrata). Chicago: 46,649 rows; NYC: 47,773 rows.
- Time window: **2026-07-06 → 2026-10-04** (last 90 days), one row per unique request
  (deduped by the city's unique request ID).
- Text is rendered from the **request's real field values** (type + street + city + zip).
- Full provenance — endpoints, exclusions (info-only types, no-address rows), and licenses — is
  documented in `backend/data/real/provenance.md`.

**The labels are HUMAN-entered, never auto-generated.**
- A **mining step only *proposes* candidates** (it never labels): e.g. "city-flagged duplicates,"
  "same address repeats," "same type but different street" (negatives). These enter a review queue as
  **pending**.
- A **human** (the admin, via the **Data & Labels** UI) marks each: duplicate / not, and relevant /
  not for each (problem, team). Every label stores **who** labelled it and **when**.
- Currently there are **298 pending duplicate-pair candidates** and a **60-problem × 8-team
  relevance grid (480 rows)** awaiting human labels. **0 are auto-labelled.**

**Gates prevent fake metrics.**
- The duplicate classifier **refuses to train** until **≥ 150** human-labelled pairs exist.
- The team ranker **refuses to train** until **≥ 100** human-labelled relevance rows exist.
- Until then, the app serves **clearly-labelled fallbacks** (cosine-threshold dedup; weighted-formula
  matching) and the admin dashboard **says so** ("no (cosine fallback)", "awaiting labels").
- **No code path invents a label, a problem, or a metric.** If data is insufficient, the system
  reports the exact shortfall instead of pretending.

> **If the professor asks "so the model isn't trained yet, is it useless?"** — Answer: the *clustering*
> component **is** trained/measured on the real corpus right now and is live. The two supervised
> components are deliberately **waiting on real human labels** because the project's rule is *never
> fabricate labels or metrics* — the machinery, splits, features, and evaluation harness are all in
> place and gated, so training happens the moment enough labels exist.

---

## Part 8 — Authentication (two user worlds)

- **Real users (Supabase Auth):**
  1. Browser signs in directly with **Supabase** (`supabase.auth.signInWithPassword`).
  2. The resulting **Supabase access token** is sent to the backend on normal channels
     (Bearer / cookie / custom header).
  3. The backend **validates that token with Supabase itself** (`GET /auth/v1/user`) — it never sees
     or stores your JWT secret.
  4. It **maps the Supabase user to a local account** (created on first login, role kept by email).
  - This is how *you* (the owner) sign in with your real account.
- **Demo accounts (local JWT):** seeded `*.civic.demo` users use a locally-signed JWT (HS256,
  12-hour expiry, token blacklisting on logout). These power the seeded demo data and work even if
  Supabase is unreachable — useful for a reliable in-front-of-a-room demo.

> **Say this:** "We support both a real hosted auth provider for production and self-contained demo
> accounts for offline demos — the same UI handles both transparently."

---

## Part 9 — Database schema (the tables)

| Table | Purpose |
|---|---|
| `users` | All accounts (citizen / team / admin), role, hashed password (demo) |
| `problems` | Citizen reports + computed fields: `is_duplicate`, `duplicate_of_id`, `duplicate_score`, cluster, status |
| `teams` | Student teams: name, description, skills, interests, experience |
| `team_members` | Member names + roles per team |
| `matches` | (problem, team) recommendation rows: score, status (suggested/accepted/rejected), explanation |
| `problem_clusters` | The active clusters + member lists |
| `notifications` | Per-user notifications (new message, team accepted, etc.) |
| `messages` | Threaded messages between citizens and teams |
| `feedback` | 👍/👎 on AI matches + free comments |
| `real_problems` | **94,422 real 311 records** (the training corpus in the DB) |
| `real_pairs` | Candidate duplicate pairs + **human label** (nullable = pending) + who/when |
| `real_relevance` | (real problem, team) rows + **human label** (nullable = pending) + who/when |
| `eval_pairs` / `eval_relevance` | Labelled evaluation rows for live P/R/F1 & P@K |
| `model_state` | Key/value store (e.g. a tuned threshold) |

**Current live counts** (as of this guide): 13 users, 33 problems, 8 teams, 136 matches,
8 clusters, **94,422 real problems**, 298 real pairs (0 labelled), 480 real relevance rows (0 labelled).

---

## Part 10 — API design (mounted under `/api`)

- **Auth:** `POST /api/auth/login` (demo), `GET /api/auth/me` (resolves both demo JWT and Supabase
  tokens), `POST /api/auth/logout`.
- **Problems:** `POST /api/problems` (submit → full analysis back), `GET /api/problems`,
  `GET /api/problems/{id}`, `GET /api/ai/analysis/{id}` (full NLP/ML transparency).
- **AI:** `POST /api/ai/check-duplicate` (method + probability), `GET /api/ai/clusters`,
  `GET /api/ai/recommend-teams/{id}`.
- **Teams:** `GET /api/teams`, `GET /api/teams/{id}`, `GET /api/teams/my-recommendations`,
  `POST /api/teams/matches/{id}/decision` (accept/reject), messaging endpoints.
- **Admin:** `GET /api/admin/statistics`, `GET /api/admin/model-performance` (incl. `trained_models`
  + `labeling`), `GET /api/admin/charts/{kind}` (PNG), **human labelling** under `GET/POST
  /api/labels/*` (status, pairs, relevance, mine, retrain).
- **Misc:** `GET /api/stats/summary`, `/api/feedback`, `/api/notifications`.

Every route is **role-gated** (citizen / team / admin) and **documented** via FastAPI's automatic
OpenAPI docs at `/docs` — *you can show the professor the live API docs in the browser.*

---

## Part 11 — Frontend (pages, roles, and features)

- **Landing** — public hero + live stats (`/api/stats/summary`).
- **Login / Register** — handles both Supabase real accounts and demo accounts automatically by email.
- **Citizen:** *My Problems* (with unique/duplicate filters), *Submit Problem*, *Problem detail*
  (NLP tokens, keywords, duplicate method + probability, similar problems, cluster, per-team scores
  + reasons, status, message the team, give feedback).
- **Team:** *Team Home* (edit profile: skills/interests/experience/members, delete team),
  **Recommended** (Suggested/Accepted/Rejected/All tabs, accept/reject, 👍/👎, live location),
  *Teams Directory*.
- **Admin:** *Admin Dashboard* — stat cards, **server-rendered analytics charts**, **AI/ML
  performance** (live metrics + trained-model status), **Data & Labels** (label real pairs +
  relevance, "Mine more", "Train models now"), problem **clusters**, user **feedback**, recent problems.
- **Cross-cutting:** dual **light/dark theme**, **glassmorphism** styling, **toasts** for actions,
  **notification bell** with unread badge, **responsive** layout with a mobile drawer, **browser-aware
  back/forward**.

---

## Part 12 — Real, measured numbers (use these as evidence)

| Metric | Value | Source |
|---|---|---|
| Real training rows | **94,422** (Chicago 46,649 + NYC 47,773) | `backend/data/real/` |
| Clustering sample | stratified **15,000** real requests | `cluster_compare.py` |
| **Selected cluster method** | **K-Means, k=12** | `artifacts/cluster_config.json` |
| K-Means silhouette / ARI | 0.2788 / **0.5406** (vs city categories) | measured |
| DBSCAN best silhouette / ARI / noise | 0.5513 / 0.3060 / 30.9% | measured |
| Embedding model | all-MiniLM-L6-v2, **384-dim**, CPU | `app/ml/embed.py` |
| Dedup fallback threshold | **0.75** cosine | `app/config.py` |
| Matching weights (semantic) | **0.60·text + 0.35·coverage + 0.05·exp** | `app/config.py` |
| Dedup supervised gate | **≥ 150** human-labelled pairs | `MIN_LABELS_DEDUP` |
| Ranker supervised gate | **≥ 100** human-labelled rows | `MIN_LABELS_RELEVANCE` |
| Current pending label work | 298 pairs + 480 relevance rows | DB counts |

> Frame it: "Clustering is **measured and live** on the real data. The two supervised models are
> **fully built and gated**, and will report real held-out metrics the moment real human labels exist."

---

## Part 13 — Live demo talk track (rehearse this once)

Do this **live** in the browser, narrating as you go:

1. **Log in as a citizen** (`citizen1@civic.demo` / `demo123`).
   *"This is the citizen view — every report is analysed the moment it's stored."*
2. Open **Submit Problem**. Type a new report, e.g.
   *"Street light not working near the bus stand on Model Town road, very dark at night."*
   Submit.
   *"Watch what just happened in the background — the pipeline ran preprocessing, embedded the text
   into 384 dimensions, compared it to every stored problem, and produced a duplicate verdict, a
   cluster, and team recommendations."*
3. Open the **problem detail**. Point to:
   - the **NLP** tokens + top keywords,
   - the **duplicate verdict** with **method + probability**,
   - the **similar problems**,
   - the **cluster** it landed in,
   - the **top teams** with each **reason** ("covers 80% of the problem's key terms…").
   *"Notice the explanation is in plain English — a team can tell *why* they were matched."*
4. **Log in as a team** (`team1@civic.demo` / `demo123`). Open **Recommended**.
   *"The problem appears here because this team's skills match it. I accept it…"*
   Click **Accept**.
   *"The problem is now assigned to us, and the citizen will be notified."*
5. **Log in as admin** (`admin@civic.demo` / `admin123`). Open **Admin Dashboard**.
   - Point to **stat cards + charts** ("live, rendered server-side"),
   - **AI/ML performance** — "it tells you exactly which method is active and its metrics,"
   - **Data & Labels** — "this is where **real** labels are entered; the models train only on these,"
   - **Clusters** — "grouped by the measured best algorithm."
6. **Open the API docs** at `/docs` (in a second tab).
   *"Every endpoint is typed, role-protected, and auto-documented."*

Close with the one-liner from Part 1.

---

## Part 14 — Expected professor questions & how to answer

**Q: Is the data real?**
> Yes. 94,422 distinct service requests from the official Chicago and NYC 311 open-data APIs, last 90
> days, deduped by the city's unique request ID, with endpoints and licenses in
> `data/real/provenance.md`. No synthetic problems.

**Q: Where do the training labels come from?**
> From **humans**, via the admin Data & Labels UI. A mining step only *proposes* candidate pairs; a
> person marks them. Every label records who and when. Nothing is auto-labelled, and the supervised
> models refuse to train below a minimum label count.

**Q: Why do you have a cosine "fallback" instead of just the trained model?**
> Because we won't fabricate a trained model we haven't legitimately trained. The fallback is a
> correct, simple baseline, it's clearly labelled in the UI, and it keeps the app fully functional
> today. The moment real labels hit the gate, the supervised model takes over and the dashboard
> reports which one is active.

**Q: How do you avoid data leakage in the splits?**
> Dedup pairs are split at the **(source, category, street) bucket level** — a real request never
> lands in two splits; a pair is only used if both of its buckets are in the same split. Team-matching
> rows are split **by problem** so all of a problem's team rows stay together. Thresholds and model
> selection use the **validation** split; final numbers come from the **test** split only.

**Q: How does duplicate detection actually work?**
> Embed both texts, compute cosine similarity plus lexical features (Porter uni/bigram Jaccard,
> length, same-category). A threshold or a supervised classifier on those features decides. We always
> show the **method and probability** so it's auditable.

**Q: Why K-Means and not DBSCAN (or vice-versa)?**
> We didn't pick by preference — we measured both on a 15k-sample of the real corpus. K-Means k=12
> achieved a higher Adjusted Rand Index against the city's own category field (0.54 vs 0.31) and
> produced no noise; DBSCAN was compact but flagged 31–70% as noise and captured less of the true
> structure. The measured winner is stored in `cluster_config.json`.

**Q: What's the difference between the embedder and TF-IDF?**
> TF-IDF is a statistical word-importance vector (fast, deterministic, lexical). The Sentence-
> Transformer produces a 384-dim *semantic* vector where meaning-similar texts are geometrically
> close even with different words. We use the semantic model by default and TF-IDF as a fallback, and
> we can run both and compare.

**Q: How is explainability achieved?**
> The team score is a weighted sum of **interpretable** components (text similarity, keyword
> coverage, experience), and we surface the **matched keywords** plus a generated **plain-English
> reason**. The user never just sees an opaque number.

**Q: How is authentication secured?**
> Real users go through **Supabase Auth**; the backend validates their token *with Supabase* and
> never holds the signing secret. Demo accounts use a locally-signed, expiring JWT with logout
> blacklisting. All routes are role-gated.

**Q: Can this scale / go to production?**
> The DB is one env-var away from **Supabase/Postgres**. The embedder runs on CPU and is cached.
> The API is stateless and containerisable. Clustering on the full corpus is batch; per-request
> work is a matrix multiply against cached vectors.

**Q: What would you improve next?**
> (1) Collect the remaining human labels to train the supervised dedup + ranker and report real
> held-out metrics. (2) Add active-learning so the labeler sees the *most informative* candidates
> first. (3) Temporal clustering (when problems recur) and geospatial clustering. (4) Multilingual
> support. (5) A public "status" API for cities.

**Q: What are the limitations today?**
> The two supervised models are pending real human labels (by design, to avoid fake metrics); the
> clustering ARI is a proxy for "does structure match the city's categories"; and embeddings of very
> short civic texts can be noisy, which is why we combine them with lexical features.

---

## Part 15 — What's real vs. pending (the honesty table — show this if asked)

| Item | Status |
|---|---|
| Real 311 corpus (94,422 rows) | **Real & ingested** |
| NLP preprocessing + Porter stemming | **Real** |
| Sentence embeddings (MiniLM, 384-d) | **Real pretrained model** |
| Clustering (K-Means k=12, measured selection) | **Measured on real data, live** |
| Duplicate detection (active) | **Cosine-threshold fallback** (supervised model gated on labels) |
| Team matching (active) | **Weighted explainable formula** (learned ranker gated on labels) |
| Duplicate / relevance labels | **Human-entered only** (298 pairs + 480 rows pending) |
| Live predictions on the UI | **Real** (computed by the running pipeline) |
| Supabase real-user auth | **Real** |
| Demo accounts | **Real** (seeded, local JWT) |

---

## Appendix A — Where each thing lives in the code (if asked to show)

- Pipeline (the background engine): `backend/app/pipeline.py`
- Preprocessing: `backend/app/ml/preprocess.py`
- Embeddings: `backend/app/ml/embed.py`
- Duplicate logic: `backend/app/ml/dedup.py`
- Clustering: `backend/app/ml/cluster.py` + `backend/artifacts/cluster_config.json`
- Team matching + explanations: `backend/app/ml/matching.py`
- Model loading + fallbacks: `backend/app/ml/model_store.py`
- Human labelling API: `backend/app/routers/labels.py`
- Real corpus + provenance: `backend/data/real/` (`provenance.md`)
- Training scripts (gated): `backend/scripts/train_dedup.py`, `train_ranker.py`,
  `cluster_compare.py`, `ingest_real.py`, `label_mining.py`, `train_all.py`
- Measured model report: `backend/artifacts/model_report.json` + `docs/MODEL_SELECTION.md`
- Frontend pages: `frontend/src/pages/*` (Admin, ProblemDetail, TeamRecommended, TeamDashboard…)
- Auth (frontend): `frontend/src/auth.jsx` + `frontend/src/supabase.js`

## Appendix B — Demo credentials

| Role | Email | Password |
|---|---|---|
| Admin | `admin@civic.demo` | `admin123` |
| Citizen | `citizen1@civic.demo` / `citizen2@civic.demo` | `demo123` |
| Teams | `team1@civic.demo` … `team8@civic.demo` | `demo123` |

(Your own real Supabase account also works for login/registration.)
