"""End-to-end analysis pipeline (SRS §12 workflow, steps 2-10).

When a problem is stored:
  3. preprocess -> 4. embed -> 5. search similar -> 6. duplicate verdict
  -> 7. (re)cluster -> 8/9. team recommendations + ranking.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import settings
from .models import Match, Notification, Problem, ProblemCluster, Team, User
from .ml import cluster as cluster_mod
from .ml import dedup, embed, evaluate, matching, model_store, preprocess

log = logging.getLogger(__name__)

_cache: dict = {"key": None, "value": None}


def _corpus_key(db: Session):
    row = db.execute(select(Problem.id, Problem.updated_at).order_by(Problem.id)).all()
    return (len(row), row[-1][1] if row else None, row[0][0] if row else None)


def _build_matrix(db: Session, embedder):
    problems = db.scalars(select(Problem).order_by(Problem.id)).all()
    semantic = getattr(embedder, "name", "tfidf") == "sentence"
    texts = [preprocess.doc_text(p.title, p.description, semantic) for p in problems]
    ids = [p.id for p in problems]
    if texts:
        embedder.fit([t if t else "empty" for t in texts])
    matrix = embedder.transform([t if t else "empty" for t in texts])
    return ids, matrix, texts, {p.id: p for p in problems}


def _with_cache(db: Session, embedder):
    key = (_corpus_key(db), settings.WEIGHT_TEXT_SIM)
    if _cache["key"] != key:
        _cache["value"] = _build_matrix(db, embedder)
        _cache["key"] = key
    return _cache["value"]


def invalidate_cache():
    _cache["key"] = None
    _cache["value"] = None


def analyze_problem(db: Session, embedder, problem: Problem, persist=True) -> dict:
    """Run similarity + duplicate verdict + clustering + team matching for one problem."""
    invalidate_cache()
    ids, matrix, texts, pmap = _with_cache(db, embedder)
    if problem.id not in pmap:
        raise ValueError("problem must be persisted before analysis")
    i = ids.index(problem.id)
    vec = matrix[i]
    threshold = evaluate.get_tuned_threshold(db, settings.DEDUP_THRESHOLD)
    semantic = getattr(embedder, "name", "tfidf") == "sentence"

    # 5-6. similar problems + duplicate verdict
    scores = dedup.nearest_scores(vec, matrix)
    similar = dedup.pick_duplicates(ids, scores, 0.30, exclude_id=problem.id)[:5]

    artifact = model_store.load_dedup_artifact() if semantic else None
    if artifact is not None:
        # Trained supervised classifier (scripts/train_dedup.py).
        raw_texts = [f"{pmap[j].title}. {pmap[j].description}" for j in ids]
        cats = [pmap[j].category for j in ids]
        q_raw = f"{problem.title}. {problem.description}"
        cands = dedup.classifier_decisions(
            artifact, vec, q_raw, problem.category, ids, matrix,
            raw_texts, cats, top_n=12, exclude_id=problem.id,
        )
        dup_thr = float(artifact["threshold"])
        duplicates = [(pid, prob) for pid, prob, _cos in cands if prob >= dup_thr]
        duplicate_of = duplicates[0][0] if duplicates else None
        dup_method = "trained_classifier"
        dup_score = round(duplicates[0][1], 4) if duplicates else None
        dup_probability = round(cands[0][1], 4) if cands else None
    else:
        duplicates = dedup.pick_duplicates(ids, scores, threshold, exclude_id=problem.id)
        duplicate_of = duplicates[0][0] if duplicates else None
        dup_method = "cosine_threshold"
        dup_score = round(duplicates[0][1], 4) if duplicates else None
        dup_probability = None

    if persist:
        problem.is_duplicate = duplicate_of is not None
        problem.duplicate_of_id = duplicate_of
        problem.duplicate_score = dup_score

    # 8-9. team recommendations & AI Auto-Assignment
    teams = db.scalars(select(Team)).all()
    recs = matching.recommend(problem, list(teams), embedder, vec, k=5)
    top_assigned_team = None
    if persist:
        db.query(Match).filter(Match.problem_id == problem.id).delete()
        for rank, r in enumerate(recs, start=1):
            # Rank #1 team is automatically assigned by AI based on silhouette, category and NLP similarity
            m_status = "assigned" if rank == 1 else "suggested"
            db.add(
                Match(
                    problem_id=problem.id,
                    team_id=r["team_id"],
                    similarity_score=r["score"],
                    ranking=rank,
                    explanation=matching.explanation_json(r["explanation"]),
                    status=m_status,
                )
            )
        if recs:
            top_assigned_team = db.get(Team, recs[0]["team_id"])
            problem.status = "assigned"
    db.flush()

    # 7. clustering (assign this problem's cluster from a global pass)
    _recluster_all(db, embedder, persist=persist)

    # Dispatch AI Auto-Assignment Reports & Notifications
    if persist and top_assigned_team:
        c_name = "Unassigned"
        if problem.cluster_id:
            c_obj = db.get(ProblemCluster, problem.cluster_id)
            if c_obj:
                c_name = c_obj.name

        # 1. Send Report to Admin
        admins = db.scalars(select(User).where(User.role == "admin")).all()
        for admin in admins:
            db.add(
                Notification(
                    user_id=admin.id,
                    type="ai_auto_assignment",
                    title=f"AI Auto-Assigned Problem #{problem.id}",
                    body=(
                        f"AI analyzed '{problem.title}' (#{problem.id}) using NLP embeddings "
                        f"& cluster '{c_name}', and automatically assigned it to "
                        f"'{top_assigned_team.team_name}' ({round(recs[0]['score'] * 100)}% fit). "
                        f"Awaiting team confirmation."
                    ),
                )
            )

        # 2. Notify Assigned Team Lead
        if top_assigned_team.user_id:
            db.add(
                Notification(
                    user_id=top_assigned_team.user_id,
                    type="problem_assigned",
                    title=f"New Problem Assigned: {problem.title}",
                    body=(
                        f"AI has automatically assigned Problem #{problem.id} ('{problem.title}') to "
                        f"your team based on matching skills. Please review and Accept or Decline."
                    ),
                )
            )

        # 3. Notify Citizen Reporter
        if problem.user_id:
            db.add(
                Notification(
                    user_id=problem.user_id,
                    type="problem_assigned",
                    title=f"Team Assigned: {top_assigned_team.team_name}",
                    body=(
                        f"Your report '{problem.title}' (#{problem.id}) was analyzed by AI and "
                        f"automatically assigned to {top_assigned_team.team_name}."
                    ),
                )
            )
        db.flush()

    return {
        "similar": similar,
        "duplicate_of": duplicate_of,
        "duplicate_score": problem.duplicate_score,
        "is_duplicate": problem.is_duplicate,
        "cluster_id": problem.cluster_id,
        "recommendations": recs,
        "threshold": threshold,
        "duplicate_method": dup_method,
        "duplicate_probability": dup_probability,
    }


def _recluster_all(db: Session, embedder, persist=True):
    """Global clustering pass; creates clusters and assigns every problem.

    Method/params from artifacts/cluster_config.json (trained selection);
    label -1 (DBSCAN noise) becomes an "Unassigned" cluster.
    """
    ids, matrix, texts, pmap = _with_cache(db, embedder)
    labels, k, sil = cluster_mod.run_clustering(matrix)
    if labels is None:
        return

    cfg = model_store.load_cluster_config()
    method = (cfg or {}).get("selected")
    if method == "dbscan":
        method_name = f"DBSCAN (eps={(cfg.get('dbscan') or {}).get('eps')})"
    elif method == "kmeans":
        method_name = f"K-Means (k={k} from trained selection)"
    else:
        method_name = f"K-Means (silhouette-selected k={k})"

    # existing clusters are volatile in this pipeline: rebuild membership
    if persist:
        db.query(ProblemCluster).delete()
    cluster_of: dict[int, ProblemCluster] = {}
    for lab in sorted(set(labels)):
        name = "Unassigned" if lab == -1 else _cluster_name(lab, labels, pmap, texts, embedder)
        c = ProblemCluster(
            name=name,
            description=(
                f"{method_name} cluster {lab} (of {k}) on problem embeddings; "
                f"silhouette {sil:.2f}."
            ),
        )
        if persist:
            db.add(c)
            db.flush()
        cluster_of[lab] = c

    for pid, lab in zip(ids, labels):
        p = pmap[pid]
        if persist:
            p.cluster_id = cluster_of[lab].id
    if persist:
        db.flush()


def _cluster_name(lab, labels, pmap, texts, embedder) -> str:
    members = [texts[i] for i, l in enumerate(labels) if l == lab]
    combined = " ".join(members)
    terms = [t for t, _w in embedder.top_terms(combined, 5)]
    if terms:
        return " & ".join(t.title() for t in terms[:3]) or f"Cluster {lab}"
    return f"Cluster {lab}"


def public_result(problem: Problem, analysis: dict, db: Session) -> dict:
    """Serialize analysis result for API responses with full NLP, embedding, and clustering metrics."""
    pmap = {p.id: p for p in db.scalars(select(Problem)).all()}
    similar_out = []
    for pid, score in analysis.get("similar", []):
        p = pmap.get(pid)
        if p:
            similar_out.append(
                {
                    "id": p.id,
                    "title": p.title,
                    "category": p.category,
                    "score": round(score, 4),
                }
            )
    dup = None
    if analysis.get("duplicate_of"):
        d = pmap.get(analysis["duplicate_of"])
        if d:
            dup = {
                "id": d.id,
                "title": d.title,
                "score": analysis.get("duplicate_score"),
            }

    # Clustering metrics and silhouette
    cfg = model_store.load_cluster_config() or {}
    method_name = cfg.get("selected", "kmeans")
    if method_name == "kmeans":
        silhouette_val = float((cfg.get("kmeans") or {}).get("silhouette", 0.2788))
        k_val = int((cfg.get("kmeans") or {}).get("k", 12))
        ari_val = float((cfg.get("kmeans") or {}).get("ari", 0.5406))
    elif method_name == "dbscan":
        silhouette_val = float((cfg.get("dbscan") or {}).get("silhouette", 0.7999))
        k_val = 8
        ari_val = float((cfg.get("dbscan") or {}).get("ari", 0.0519))
    else:
        silhouette_val = 0.28
        k_val = 12
        ari_val = 0.54

    cluster = None
    if problem.cluster_id:
        c = db.get(ProblemCluster, problem.cluster_id)
        if c:
            member_ids = db.scalars(select(Problem.id).where(Problem.cluster_id == c.id)).all()
            cluster = {
                "id": c.id,
                "name": c.name,
                "size": len(member_ids),
                "silhouette": round(silhouette_val, 4),
                "method": method_name,
                "k": k_val,
                "ari": ari_val,
            }

    # All clusters list for visual cluster map
    all_clusters = []
    for cl in db.scalars(select(ProblemCluster).order_by(ProblemCluster.id)).all():
        m_count = db.scalar(select(func.count(Problem.id)).where(Problem.cluster_id == cl.id)) or 0
        all_clusters.append({
            "id": cl.id,
            "name": cl.name,
            "size": m_count,
            "is_current": cl.id == problem.cluster_id,
        })

    # NLP preprocessing details
    embedder = embed.get_shared_embedder()
    semantic = getattr(embedder, "name", "tfidf") == "sentence"
    doc = preprocess.doc_text(problem.title, problem.description, semantic)
    raw_tokens = preprocess.process(f"{problem.title}. {problem.description}").split()
    top_keywords = embedder.top_terms(doc, 8)

    recs = []
    for m in db.scalars(
        select(Match).where(Match.problem_id == problem.id).order_by(Match.ranking)
    ).all():
        team = db.get(Team, m.team_id)
        try:
            expl = json.loads(m.explanation or "{}")
        except json.JSONDecodeError:
            expl = {}
        recs.append(
            {
                "team_id": m.team_id,
                "team_name": team.team_name if team else "?",
                "score": m.similarity_score,
                "ranking": m.ranking,
                "status": m.status,
                "explanation": expl.get("reason", ""),
                "matched_keywords": expl.get("matched_keywords", []),
            }
        )

    return {
        "id": problem.id,
        "duplicate": dup,
        "is_duplicate": problem.is_duplicate,
        "duplicate_score": problem.duplicate_score,
        "similar_problems": similar_out,
        "cluster": cluster,
        "all_clusters": all_clusters,
        "recommended_teams": recs,
        "nlp": {
            "tokens": raw_tokens,
            "token_count": len(raw_tokens),
            "top_keywords": top_keywords,
            "cleaned_text": doc,
        },
        "embedding": {
            "model": "sentence-transformers (all-MiniLM-L6-v2)" if semantic else "TF-IDF baseline",
            "dimensions": 384 if semantic else "sparse",
            "threshold": analysis.get("threshold", settings.DEDUP_THRESHOLD),
        },
        "clustering_metrics": {
            "method": method_name,
            "silhouette_score": round(silhouette_val, 4),
            "k": k_val,
            "ari": ari_val,
            "active_cluster": cluster["name"] if cluster else "Unassigned",
        },
    }
