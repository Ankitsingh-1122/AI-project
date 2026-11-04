"""Unit tests for the AI/ML engine (preprocessing, dedup tuning, clustering, matching)."""

import numpy as np
import pytest

from app.ml import cluster as cluster_mod
from app.ml import dedup, preprocess
from app.ml.embed import TfidfEmbedder, cosine


# ---- preprocessing ---------------------------------------------------------


def test_preprocess_lowercases_and_strips_punctuation():
    out = preprocess.process("The Street Light IS broken!!! Please fix it...")
    assert "street" in out
    assert "light" in out
    assert "broken" in out
    assert "the" not in out.split()
    assert "is" not in out.split()


def test_preprocess_removes_stopwords():
    out = preprocess.process("there is a huge pothole on the road near the market")
    tokens = out.split()
    assert "pothole" in tokens
    assert "road" in tokens
    assert "there" not in tokens
    assert "a" not in tokens


def test_preprocess_normalizes_suffixes():
    out = preprocess.process("The streetlamp has stopped working.")
    assert "streetlamp" in out
    assert "stop" in out  # stopped -> stop
    assert "work" in out  # working -> work


# ---- tfidf embedder --------------------------------------------------------


def test_tfidf_transform_shapes_and_cosine():
    docs = [
        "street light broken",
        "street lamp not working",
        "garbage pile overflowing",
    ]
    emb = TfidfEmbedder().fit(docs)
    m = emb.transform(docs)
    assert m.shape == (3, m.shape[1])
    # semantically close pair should score above unrelated pair
    close = cosine(m[0], m[1])
    far = cosine(m[0], m[2])
    assert close > far


def test_tfidf_top_terms():
    emb = TfidfEmbedder().fit(
        [
            "street light broken",
            "street lamp not working",
            "garbage pile overflowing",
            "pothole on main road",
        ]
    )
    terms = [t for t, _ in emb.top_terms("street light broken", k=3)]
    assert any("light" in t for t in terms)


# ---- dedup threshold tuning -------------------------------------------------


def test_tune_threshold_separates_duplicates():
    # realistic corpus: 4 duplicate pairs among 16 varied problems
    docs = [
        "street light broken near bus stand",
        "street lamp not working near the bus stand area",
        "garbage pile overflowing in colony",
        "garbage not collected for a week in our colony",
        "pothole on main bazaar road",
        "deep pothole causing accidents on bazaar road",
        "water supply stopped in sector",
        "no drinking water coming from taps in sector",
        "traffic signal not working at crossing",
        "sewage overflowing on residential street",
        "broken bench in central park",
        "street light flickering on phase road",
        "dog menace in night on main road",
        "overgrown trees blocking the road view",
        "illegal construction on public land",
        "drain blocked near vegetable market",
    ]
    emb = TfidfEmbedder().fit(docs)
    m = emb.transform(docs)
    pairs = [(0, 1, True), (2, 3, True), (4, 5, True), (6, 7, True),
             (0, 4, False), (0, 12, False), (2, 9, False), (11, 0, False)]
    scores = {(a, b): float(cosine(m[a], m[b])) for a, b, _ in pairs}
    labels = {(a, b): dup for a, b, dup in pairs}
    thr, f1 = dedup.tune_threshold(scores, labels)
    assert 0.10 <= thr <= 0.97
    assert f1 >= 0.8  # labelled set is separable on this corpus
    # every duplicate pair must score above every unrelated pair (separability)
    assert min(v for (a, b), v in scores.items() if labels[(a, b)]) > max(
        v for (a, b), v in scores.items() if not labels[(a, b)]
    )


def test_pick_duplicates_respects_threshold_and_exclusion():
    ids = [1, 2, 3]
    scores = np.array([0.95, 0.5, 0.85])
    out = dedup.pick_duplicates(ids, scores, 0.8, exclude_id=3)
    assert out == [(1, pytest.approx(0.95))]


# ---- clustering -------------------------------------------------------------


def test_clustering_renders_two_groups(monkeypatch):
    # Fallback path: no trained cluster config -> silhouette-based k search.
    from app.ml import model_store

    monkeypatch.setattr(model_store, "load_cluster_config", lambda: None)
    rng = np.random.default_rng(0)
    a = rng.normal(0, 0.1, size=(6, 8)) + np.zeros(8)
    b = rng.normal(0, 0.1, size=(6, 8)) + np.ones(8) * 5
    m = np.vstack([a, b])
    labels, k, sil = cluster_mod.run_clustering(m)
    assert labels is not None
    # the two synthetic groups must be separated (order may swap)
    same = all(labels[i] == labels[i + 1] for i in range(5))
    split = all(labels[i] != labels[i + 6] for i in range(6))
    assert same and split


def test_clustering_uses_trained_kmeans_config(monkeypatch):
    from app.ml import model_store

    monkeypatch.setattr(
        model_store, "load_cluster_config",
        lambda: {"selected": "kmeans", "kmeans": {"k": 2}, "dbscan": {}},
    )
    rng = np.random.default_rng(0)
    a = rng.normal(0, 0.1, size=(6, 8)) + np.zeros(8)
    b = rng.normal(0, 0.1, size=(6, 8)) + np.ones(8) * 5
    m = np.vstack([a, b])
    labels, k, sil = cluster_mod.run_clustering(m)
    assert k == 2  # configured k, not silhouette-searched
    same = all(labels[i] == labels[i + 1] for i in range(5))
    split = all(labels[i] != labels[i + 6] for i in range(6))
    assert same and split


def test_clustering_dbscan_config_marks_noise(monkeypatch):
    from app.ml import model_store

    monkeypatch.setattr(
        model_store, "load_cluster_config",
        lambda: {"selected": "dbscan", "kmeans": {},
                 "dbscan": {"eps": 0.05, "min_samples": 5}},
    )
    rng = np.random.default_rng(2)
    blob = rng.normal(0, 0.01, size=(8, 4))
    outlier = np.array([[10.0, 10.0, 10.0, 10.0]])
    m = np.vstack([blob, outlier])
    labels, k, sil = cluster_mod.run_clustering(m)
    assert labels.count(-1) == 1  # the isolated point is noise
    assert labels.count(labels[0]) == 8


def test_cluster_purity_perfect_and_mixed():
    assert cluster_mod.cluster_purity([0, 0, 1, 1], ["a", "a", "b", "b"]) == 1.0
    assert 0.5 <= cluster_mod.cluster_purity([0, 0, 0, 0], ["a", "a", "b", "b"]) <= 0.5 + 1e-9
    assert cluster_mod.cluster_purity([0, 0, 0, 0], ["a", "b", "a", "b"]) == 0.5


def test_clustering_insufficient_data():
    m = np.random.default_rng(1).normal(size=(3, 4))
    labels, k, sil = cluster_mod.run_clustering(m)
    assert labels is None


# ---- trained artifact integration -------------------------------------

def test_model_summary_structure():
    from app.ml import model_store

    s = model_store.model_summary()
    assert set(s) >= {"dedup_classifier", "team_ranker", "clustering", "artifacts_dir", "retrain"}
    assert isinstance(s["dedup_classifier"], dict)
    assert isinstance(s["team_ranker"], dict)
    assert isinstance(s["clustering"], dict)


def test_load_dedup_artifact_shape():
    from app.ml import model_store

    art = model_store.load_dedup_artifact()
    if art is None:
        pytest.skip("dedup artifact not present")
    assert "model" in art and "threshold" in art and "features" in art
    assert len(art["features"]) == 23


def test_load_ranker_artifact_shape():
    from app.ml import model_store

    art = model_store.load_ranker_artifact()
    if art is None:
        pytest.skip("ranker artifact not present")
    assert "model" in art and "features" in art
    assert len(art["features"]) == 6


def test_ranker_features_shape_and_range():
    from app.ml import matching
    from scripts.nlp_common import ranker_features, team_profile_parts

    p = "Street light not working at Model Town since last week"
    full, sd = team_profile_parts("Smart Street Labs", "IoT street lighting monitoring",
                                  ["python", "iot"], ["street lights"], "Built a street light app.")
    vec = np.zeros(384, dtype=np.float32)
    vec[0] = 1.0
    f = ranker_features(p, full, sd, "Built a street light app.", vec, vec)
    assert len(f) == 6
    # identical vectors -> cosine similarity 1
    assert f[0] == pytest.approx(1.0)
    assert 0.0 <= f[4] <= 1.0  # coverage in [0,1]
    assert f[5] in (0.0, 1.0)  # exp bonus binary


def test_ranker_score_returns_probability():
    from app.ml import matching, model_store

    art = model_store.load_ranker_artifact()
    if art is None:
        pytest.skip("ranker artifact not present")
    f = [0.5, 0.1, 0.0, 0.2, 0.3, 0.0]
    prob = matching.ranker_score(art, None, None, f)
    assert 0.0 <= prob <= 1.0


def test_classifier_decisions_exclusion_and_sort():
    from app.ml import dedup, model_store

    art = model_store.load_dedup_artifact()
    if art is None:
        pytest.skip("dedup artifact not present")
    # 3 synthetic 384-dim unit vectors; make them distinct
    rng = np.random.default_rng(3)
    mat = rng.normal(size=(3, 384)).astype(np.float32)
    mat /= np.linalg.norm(mat, axis=1, keepdims=True)
    q = mat[0].copy()
    ids = [10, 11, 12]
    texts = ["Pothole near main road", "Garbage dumped at park", "Street light broken"]
    cats = ["pothole", "garbage", "street_light"]
    out = dedup.classifier_decisions(
        art, q, "Pothole near main road", "pothole",
        ids, mat, texts, cats, top_n=12, exclude_id=10,
    )
    # excluded id 10 must not appear
    assert 10 not in [pid for pid, _p, _c in out]
    # sorted by probability desc
    probs = [p for _pid, p, _c in out]
    assert probs == sorted(probs, reverse=True)
    assert all(0.0 <= p <= 1.0 for p in probs)
