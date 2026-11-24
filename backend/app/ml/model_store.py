"""Lazy loader for trained model artifacts (backend/artifacts/).

Training and serving share this single store: scripts/train_*.py writes the
artifacts, the running app reads them. If an artifact is missing or the app
is launched with CIVIC_NO_MODELS=1, callers fall back to the classic
cosine/formula behaviour so the service degrades gracefully.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

ART_DIR = Path(__file__).resolve().parents[2] / "artifacts"

_dedup = {"loaded": False, "value": None}
_ranker = {"loaded": False, "value": None}
_cluster = {"loaded": False, "value": None}


def _disabled() -> bool:
    return os.environ.get("CIVIC_NO_MODELS", "") == "1"


def _load_joblib(name: str, cache: dict):
    if cache["loaded"]:
        return cache["value"]
    cache["loaded"] = True
    if _disabled():
        return None
    path = ART_DIR / name
    if not path.exists():
        return None
    try:
        import joblib

        value = joblib.load(path)
        cache["value"] = value
        log.info("loaded model artifact %s", path)
        return value
    except Exception:  # noqa: BLE001 - a broken artifact must not kill the API
        log.exception("failed to load %s; falling back to defaults", path)
        return None


def load_dedup_artifact() -> dict | None:
    """{model, threshold, features, categories, params, model_name, metrics}"""
    return _load_joblib("dedup_model.joblib", _dedup)


def load_ranker_artifact() -> dict | None:
    """{model, scaler, features, model_name}"""
    return _load_joblib("ranker.joblib", _ranker)


def load_cluster_config() -> dict | None:
    if _cluster["loaded"]:
        return _cluster["value"]
    _cluster["loaded"] = True
    if _disabled():
        return None
    path = ART_DIR / "cluster_config.json"
    if not path.exists():
        return None
    try:
        with open(path) as f:
            cfg = json.load(f)
        _cluster["value"] = cfg
        return cfg
    except Exception:  # noqa: BLE001
        log.exception("failed to read %s", path)
        return None


def model_summary() -> dict:
    """What the live service is currently running (admin endpoint)."""
    dedup = load_dedup_artifact()
    ranker = load_ranker_artifact()
    cluster = load_cluster_config()

    ranker_metrics = None
    ranker_metrics_path = ART_DIR / "ranker_metrics.json"
    if ranker_metrics_path.exists():
        try:
            with open(ranker_metrics_path) as f:
                ranker_metrics = json.load(f)
        except Exception:
            pass

    return {
        "dedup_classifier": {
            "active": bool(dedup),
            "model": dedup.get("model_name") if dedup else None,
            "params": {k: str(v) for k, v in (dedup.get("params") or {}).items() if not k.startswith("steps")} if dedup and isinstance(dedup.get("params"), dict) else None,
            "threshold": dedup.get("threshold") if dedup else None,
            "val_auc": dedup.get("val_auc") if dedup else None,
            "test_metrics": dedup.get("metrics") if dedup else None,
        },
        "team_ranker": {
            "active": bool(ranker),
            "model": ranker.get("model_name") if ranker else None,
            "val_auc": ranker_metrics.get("auc") if ranker_metrics else None,
            "test_metrics": ranker_metrics,
        },
        "clustering": {
            "configured": bool(cluster),
            "selected": cluster.get("selected") if cluster else None,
            "kmeans_k": (cluster.get("kmeans") or {}).get("k") if cluster else None,
            "dbscan": cluster.get("dbscan") if cluster else None,
        },
        "artifacts_dir": str(ART_DIR),
        "retrain": "cd backend && HF_HOME=$HOME/.hf python -m scripts.train_all",
    }
