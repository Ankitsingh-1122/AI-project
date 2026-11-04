"""Shared NLP utilities for the training scripts.

Reuses the app's preprocessing + embedders so training and serving use the
exact same text representations. Adds a real Porter stemmer (nltk) for the
lexical features and a disk cache for sentence embeddings.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os

import joblib
import numpy as np
from nltk.stem import PorterStemmer

from app.ml import preprocess
from app.ml.embed import SentenceEmbedder

BASE = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(BASE, "data")
ART = os.path.join(BASE, "artifacts")

_stemmer = PorterStemmer()
_stop = set(preprocess.STOPWORDS)


def stem_tokens(text: str) -> set[str]:
    toks = preprocess.tokenize(preprocess.clean_text(text))
    out = set()
    for t in toks:
        if t in _stop or len(t) < 2:
            continue
        out.add(_stemmer.stem(t))
    return out


def porter_set(text: str) -> set[str]:
    return stem_tokens(text)


def bigram_set(text: str) -> set[str]:
    toks = sorted(stem_tokens(text))
    return {f"{a}_{b}" for a, b in zip(toks, toks[1:])}


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class _ST:
    """Lazy sentence-embedder with a disk cache keyed on corpus hash."""

    def __init__(self):
        self.embedder = None
        self.cache_dir = os.path.join(DATA, "cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def model(self):
        if self.embedder is None:
            self.embedder = SentenceEmbedder()
        return self.embedder

    def encode(self, texts: list[str], tag: str = "corpus") -> np.ndarray:
        key = tag + ":" + hashlib.sha1("\n".join(texts).encode()).hexdigest()[:24]
        path = os.path.join(self.cache_dir, f"emb_{key}.npy")
        if os.path.exists(path):
            return np.load(path)
        vec = self.model().transform([t if t.strip() else "empty" for t in texts])
        np.save(path, vec)
        return vec


st = _ST()


def load_csv(name: str) -> list[dict]:
    with open(os.path.join(DATA, name)) as f:
        return list(csv.DictReader(f))


def pair_text(row: dict, side: str) -> str:
    return f'{row[f"title_{side}"]}. {row[f"desc_{side}"]}'


def full_text(row: dict) -> str:
    return f'{row["title"]}. {row["description"]}'


def save_json(name: str, obj):
    with open(os.path.join(ART, name), "w") as f:
        json.dump(obj, f, indent=2, default=float)


def load_json(name: str):
    path = os.path.join(ART, name)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


CATEGORIES = [
    "street_light", "pothole", "water_supply", "sewage",
    "garbage", "traffic", "public_space", "encroachment",
]


def category_onehot(cat: str, cats: list[str] = CATEGORIES) -> list[float]:
    return [1.0 if c == cat else 0.0 for c in cats]


def pair_features(
    emb_a: np.ndarray, emb_b: np.ndarray,
    text_a: str, text_b: str,
    cat_a: str = "", cat_b: str = "",
    cats: list[str] = CATEGORIES,
) -> list[float]:
    """Feature vector for a candidate duplicate pair (serving + training)."""
    cos = float(np.dot(emb_a, emb_b))
    diff = float(np.linalg.norm(emb_a - emb_b))
    ta, tb = porter_set(text_a), porter_set(text_b)
    ga, gb = bigram_set(text_a), bigram_set(text_b)
    la, lb = max(len(text_a.split()), 1), max(len(text_b.split()), 1)
    f = [
        cos,                                   # 0 semantic cosine
        diff,                                  # 1 semantic distance
        jaccard(ta, tb),                       # 2 porter unigram overlap
        jaccard(ga, gb),                       # 3 porter bigram overlap
        min(la, lb) / max(la, lb),             # 4 length ratio
        abs(la - lb) / max(la + lb, 1),        # 5 length delta
        1.0 if (cat_a and cat_a == cat_b) else 0.0,  # 6 same category
    ]
    f += category_onehot(cat_a, cats)          # 7..14
    f += category_onehot(cat_b, cats)          # 15..22
    return f


FEATURE_NAMES = (
    ["cos_sim", "cos_dist", "uni_jaccard", "bi_jaccard", "len_ratio", "len_delta", "cat_eq"]
    + [f"cat_a_{c}" for c in CATEGORIES]
    + [f"cat_b_{c}" for c in CATEGORIES]
)


# ---------------------------------------------------------------------------
# Team-matching ranker features — SINGLE SOURCE OF TRUTH for training
# (scripts/train_ranker.py) AND serving (app/ml/matching.py). Do not change
# this list without retraining (scripts/train_all.py).
# ---------------------------------------------------------------------------
RANKER_FEATURE_NAMES = ["cos_sem", "uni_jac", "bi_jac", "skill_jac", "coverage", "exp_bonus"]

_STOP_RANKER = {
    "the", "of", "at", "in", "near", "under", "and", "or", "is", "was", "there",
    "are", "for", "since", "last", "night", "today", "not", "very", "a", "an",
    "it", "has", "been", "please", "as", "with", "its", "this", "that",
}


def content_words(text: str) -> set[str]:
    """Stemmed content words used for ranker coverage/experience features."""
    return {
        _stemmer.stem(w)
        for w in text.lower().split()
        if w.isalpha() and len(w) > 2 and _stemmer.stem(w) not in _STOP_RANKER
    }


def team_profile_parts(name, description, skills, interests, experience):
    """(full_profile_text, skills+description+interests text) — same join as
    used to build team embeddings/labels at training time."""
    full = " ".join([name or "", description or "", " ".join(skills or []),
                     " ".join(interests or []), experience or ""])
    sd = " ".join([name or "", description or "", " ".join(skills or []),
                   " ".join(interests or [])])
    return full, sd


def ranker_features(p_text: str, t_full_text: str, t_sd_text: str, t_exp_text: str,
                    p_vec: np.ndarray, t_vec: np.ndarray) -> list[float]:
    """The 6 features of the team-matching ranker (see RANKER_FEATURE_NAMES)."""
    pw = content_words(p_text)
    t_full = porter_set(t_full_text)
    return [
        float(np.dot(p_vec, t_vec)),
        jaccard(porter_set(p_text), t_full),
        jaccard(bigram_set(p_text), bigram_set(t_full_text)),
        jaccard(porter_set(p_text), porter_set(t_sd_text)),
        len(pw & t_full) / max(len(pw), 1),
        1.0 if (pw & content_words(t_exp_text)) else 0.0,
    ]
