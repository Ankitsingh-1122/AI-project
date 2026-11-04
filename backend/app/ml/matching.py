"""Problem <-> student-team matching (SRS FR-09, FR-10, FR-11, 7.6).

Score = w1 * text_similarity(problem, team_profile)
      + w2 * keyword_coverage(problem_top_terms in team skills/interests)
      + w3 * experience_bonus

Every recommendation carries a human-readable explanation: the team
keywords that matched and the score breakdown.
"""

from __future__ import annotations

import json
import re

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from . import preprocess
from .embed import TfidfEmbedder


def team_text(team, semantic: bool = False) -> str:
    """Team profile as text.

    semantic=True (sentence embedder): light cleaning only - stemmed/
    stop-word-stripped text degrades sentence embeddings.
    semantic=False (TF-IDF): full NLP pipeline.
    """
    parts = [team.team_name or "", team.description or ""]
    parts += team.skills_list
    parts += team.interests_list
    if team.experience:
        parts.append(team.experience)
    joined = " . ".join(p for p in parts if p)
    return preprocess.clean_text(joined) if semantic else preprocess.process(joined)


def _weights(semantic: bool):
    from ..config import settings

    if semantic:
        return settings.WEIGHT_TEXT_SIM_SEMANTIC, settings.WEIGHT_SKILL_OVERLAP_SEMANTIC, settings.WEIGHT_EXPERIENCE
    return settings.WEIGHT_TEXT_SIM, settings.WEIGHT_SKILL_OVERLAP, settings.WEIGHT_EXPERIENCE


def _token_set(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", preprocess.clean_text(text)))


def score_problem_team(
    problem_vec: np.ndarray,
    team_vec: np.ndarray,
    problem_keywords: list[str],
    team,
    semantic: bool = False,
) -> tuple[float, dict]:
    text_sim = float(
        cosine_similarity(problem_vec[None, :], team_vec[None, :])[0, 0]
    )
    text_sim = max(text_sim, 0.0)  # sentence models can score short texts slightly negative
    team_tokens = _token_set(team_text(team, semantic=semantic))
    matched = [kw for kw in problem_keywords if kw.split() and set(kw.split()) <= team_tokens or kw in team_tokens]
    coverage = len(matched) / len(problem_keywords) if problem_keywords else 0.0

    exp_bonus = 0.0
    if team.experience.strip():
        exp_tokens = _token_set(team.experience)
        exp_bonus = float(any(set(kw.split()) <= exp_tokens for kw in problem_keywords))

    w_text, w_skill, w_exp = _weights(semantic)
    score = w_text * text_sim + w_skill * coverage + w_exp * exp_bonus

    explanation = {
        "text_similarity": round(text_sim, 4),
        "keyword_coverage": round(coverage, 4),
        "experience_bonus": round(exp_bonus, 4),
        "matched_keywords": matched[:8],
        "team_skills": team.skills_list[:8],
        "reason": _explain(matched, text_sim, coverage, team),
    }
    return round(float(score), 4), explanation


def _explain(matched: list[str], text_sim: float, coverage: float, team) -> str:
    bits = []
    if matched:
        bits.append(
            "team skills/interests overlap problem keywords: " + ", ".join(matched[:5])
        )
    if coverage >= 0.5:
        bits.append(f"covers {int(coverage * 100)}% of the problem's key terms")
    if text_sim >= 0.4:
        bits.append(f"team profile is semantically close to the problem (sim {text_sim:.2f})")
    if not bits:
        bits.append("weak topical overlap - listed for completeness")
    bits.append(f"team: {team.team_name}")
    return ". ".join(bits) + "."


def ranker_score(artifact: dict, p_vec: np.ndarray, t_vec: np.ndarray,
                 feat_row: list[float]) -> float:
    """Apply the trained team-matching ranker to one feature row (0..1)."""
    x = np.asarray([feat_row], dtype=np.float32)
    if artifact.get("scaler") is not None:
        x = artifact["scaler"].transform(x)
    return float(artifact["model"].predict_proba(x)[0, 1])


def recommend(
    problem,
    teams: list,
    embedder: TfidfEmbedder,
    problem_vec: np.ndarray,
    k: int = 5,
) -> list[dict]:
    """Rank teams for one problem. Returns ranked dicts with explanations.

    When a trained ranker artifact exists (artifacts/ranker.joblib, see
    scripts/train_ranker.py), the FINAL score is the ranker's probability,
    computed on exactly the features the ranker was trained on. The classic
    weighted formula is kept in the explanation as `formula_score` for
    transparency. Without an artifact, the weighted formula is used (the
    previous behaviour).
    """
    if not teams:
        return []
    semantic = getattr(embedder, "name", "tfidf") == "sentence"
    p_text = (
        preprocess.clean_text(f"{problem.title}. {problem.description}")
        if semantic
        else preprocess.problem_text(problem.title, problem.description)
    )
    keywords = [t for t, _w in embedder.top_terms(p_text, 10)]
    team_texts = [team_text(t, semantic=semantic) for t in teams]
    team_texts = [t if t.strip() else "empty" for t in team_texts]
    t_matrix = embedder.transform(team_texts)
    results = []
    for i, team in enumerate(teams):
        score, explanation = score_problem_team(
            problem_vec, t_matrix[i], keywords, team, semantic=semantic
        )
        results.append(
            {
                "team_id": team.id,
                "team_name": team.team_name,
                "score": score,
                "explanation": explanation,
            }
        )

    # Trained ranker (if available): re-score with its exact training features.
    from . import model_store

    artifact = model_store.load_ranker_artifact() if semantic else None
    if artifact is not None:
        from scripts.nlp_common import ranker_features, team_profile_parts

        p_raw = f"{problem.title}. {problem.description}"
        parts = [
            team_profile_parts(t.team_name, t.description, t.skills_list,
                               t.interests_list, t.experience)
            for t in teams
        ]
        t_raws = [full if full.strip() else "empty" for full, _ in parts]
        p_rvec = embedder.transform([p_raw if p_raw.strip() else "empty"])[0]
        t_rvecs = embedder.transform(t_raws)
        for i, team in enumerate(teams):
            full, sd = parts[i]
            feat = ranker_features(p_raw, full, sd, team.experience or "",
                                   p_rvec, t_rvecs[i])
            prob = ranker_score(artifact, p_rvec, t_rvecs[i], feat)
            results[i]["explanation"]["formula_score"] = results[i]["score"]  # pre-ranker
            results[i]["score"] = round(prob, 4)
            results[i]["explanation"]["scoring_model"] = artifact.get("model_name", "ranker")
            results[i]["explanation"]["model_score"] = round(prob, 4)

    results.sort(key=lambda r: -r["score"])
    for rank, r in enumerate(results[:k], start=1):
        r["ranking"] = rank
    return results[:k]


def explanation_json(explanation: dict) -> str:
    return json.dumps(explanation, ensure_ascii=False)
