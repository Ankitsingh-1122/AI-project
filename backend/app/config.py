from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database: defaults to SQLite so the demo runs instantly.
    # Point this at Supabase/PostgreSQL to switch, e.g.
    # DATABASE_URL=postgresql+psycopg2://user:pass@host/db
    DATABASE_URL: str = "sqlite:///./civic.db"

    # Embedding model: "sentence" (sentence-transformers all-MiniLM-L6-v2,
    # default) or "tfidf" (baseline). Falls back to tfidf automatically
    # if the sentence model cannot be loaded (SRS 7.7 comparison).
    EMBEDDER: str = "sentence"

    # Duplicate-detection threshold. seed.py tunes this experimentally
    # on the labelled evaluation set and persists it in model_state;
    # this value is only the starting default.
    DEDUP_THRESHOLD: float = 0.75

    # Team-matching weights (tfidf baseline)
    WEIGHT_TEXT_SIM: float = 0.45
    WEIGHT_SKILL_OVERLAP: float = 0.50
    WEIGHT_EXPERIENCE: float = 0.05
    # Team-matching weights (sentence embeddings: semantic sim is more reliable)
    WEIGHT_TEXT_SIM_SEMANTIC: float = 0.60
    WEIGHT_SKILL_OVERLAP_SEMANTIC: float = 0.35

    JWT_SECRET: str = "dev-secret-change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12

    # Supabase Auth (real user accounts). The publishable key is a PUBLIC
    # key — safe to embed. Browser logins/registrations go to Supabase; the
    # backend validates the resulting access token via Supabase' own API
    # (GET /auth/v1/user), so no JWT secret is needed here.
    SUPABASE_URL: str = "https://trqtuxsxajdquoyanfjr.supabase.co"
    SUPABASE_PUBLISHABLE_KEY: str = "sb_publishable_AhicOJJRac4k3fqqEfJ2tA_SHljWL69"

    # Real-data ML training gates. Supervised models are trained ONLY on
    # human-labelled rows (admin "Data & Labels" UI). Below these counts the
    # API refuses to train and reports how many labels are still missing.
    MIN_LABELS_DEDUP: int = 150          # labelled duplicate pairs
    MIN_LABELS_RELEVANCE: int = 100      # labelled (problem, team) relevance rows

    # Auto-seed demo data when the database is empty (demo mode).
    SEED_ON_START: bool = True

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
