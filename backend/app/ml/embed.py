"""Text representation (SRS 7.1, 7.2): TF-IDF baseline and optional
sentence-transformer embeddings, with cosine similarity (7.3)."""

from __future__ import annotations

import logging

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

log = logging.getLogger(__name__)

SENTENCE_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


class TfidfEmbedder:
    name = "tfidf"

    def __init__(self):
        self.vectorizer = None
        self.fit_corpus: list[str] = []

    def fit(self, docs: list[str]):
        docs = [d if d.strip() else "empty" for d in docs]
        # Build + fit locally, then publish: concurrent readers (uvicorn
        # threadpool) must never observe an assigned-but-unfitted vectorizer.
        vec = TfidfVectorizer(
            max_features=2000,
            ngram_range=(1, 1),
            sublinear_tf=True,
            min_df=1,
        )
        vec.fit(docs)
        self.vectorizer = vec
        self.fit_corpus = list(docs)
        return self

    def transform(self, docs: list[str]) -> np.ndarray:
        if self.vectorizer is None:
            self.fit(docs)
        vec = self.vectorizer.transform(docs).toarray().astype(np.float32)
        return _l2_normalize(vec)

    def predict(self, doc: str) -> np.ndarray:
        return self.transform([doc])[0]

    def top_terms(self, doc: str, k: int = 10) -> list[tuple[str, float]]:
        """Keywords with TF-IDF weight for a document (used in explanations)."""
        from .preprocess import STOPWORDS

        if self.vectorizer is None or self.vectorizer.vocabulary_ is None:
            return []
        vec = self.vectorizer.transform([doc])[0]
        ranked = np.argsort(-vec.toarray().ravel())
        vocab = self.vectorizer.vocabulary_
        terms = []
        for i in ranked:
            w = float(vec.toarray().ravel()[i])
            if w <= 0:
                continue
            term = next((t for t, idx in vocab.items() if idx == i), "")
            if term in STOPWORDS or len(term) < 3:
                continue
            terms.append((term, round(w, 4)))
            if len(terms) >= k:
                break
        return terms


class SentenceEmbedder:
    name = "sentence"

    def __init__(self):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(SENTENCE_MODEL_NAME)
        self.vectorizer = TfidfEmbedder()  # for keyword extraction

    def fit(self, docs: list[str]):
        # no fitting needed for the sentence model; the TF-IDF keyword
        # extractor is fit + published atomically (see TfidfEmbedder.fit).
        tfidf = TfidfEmbedder()
        tfidf.fit([d if d.strip() else "empty" for d in docs])
        self.vectorizer = tfidf
        return self

    def transform(self, docs: list[str]) -> np.ndarray:
        docs = [d if d.strip() else "empty" for d in docs]
        vec = self.model.encode(docs, normalize_embeddings=True, show_progress_bar=False)
        return vec.astype(np.float32)

    def predict(self, doc: str) -> np.ndarray:
        return self.transform([doc])[0]

    def top_terms(self, doc: str, k: int = 10) -> list[tuple[str, float]]:
        return self.vectorizer.top_terms(doc, k)


def _l2_normalize(vec: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vec, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vec / norms


def get_embedder(prefer: str = "tfidf") -> TfidfEmbedder | SentenceEmbedder:
    """Factory with graceful fallback to TF-IDF (SRS 7.7 model switch)."""
    if prefer == "sentence":
        try:
            emb = SentenceEmbedder()
            log.info("Loaded sentence-transformer model %s", SENTENCE_MODEL_NAME)
            return emb
        except Exception as exc:  # model unavailable / download failed
            log.warning("Falling back to TF-IDF embedder: %s", exc)
    return TfidfEmbedder()


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(cosine_similarity(a[None, :], b[None, :])[0, 0])


_shared: dict = {"embedder": None, "requested": None}


def get_shared_embedder(prefer: str | None = None):
    """Process-wide embedder instance (sentence model load is expensive)."""
    from ..config import settings

    prefer = prefer or settings.EMBEDDER
    if _shared["embedder"] is None or _shared["requested"] != prefer:
        _shared["embedder"] = get_embedder(prefer)
        _shared["requested"] = prefer
    return _shared["embedder"]
