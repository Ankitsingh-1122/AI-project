"""Import the REAL 311 corpus into the DB and mine CANDIDATE duplicate pairs
for human review.

This script NEVER assigns labels. It only:
  * upserts RealProblem rows from data/real/corpus_all.csv (real records)
  * proposes candidate pairs into RealPair with is_duplicate = NULL (pending):
      - source='dup_flag'     : a Chicago record the CITY itself flagged as a
                                duplicate, paired with the closest same-type,
                                same-address record (a human confirms/refutes)
      - source='same_address' : same request type at the same street address,
                                repeated within the window
      - source='negative'     : same category, DIFFERENT address (negative
                                candidates keep the label balance realistic)
  * samples RealProblems for the team-relevance labelling grid and pre-creates
    NULL RealRelevance rows (one per team) so the UI shows a stable grid

Idempotent: re-running tops up missing candidates up to the targets.

Usage:  python -m scripts.label_mining [--pairs 200] [--relevance-problems 60]
"""
from __future__ import annotations

import argparse
import csv
import os
import random
from collections import defaultdict

from sqlalchemy import select

from app.database import SessionLocal
from app.models import RealPair, RealProblem, RealRelevance, Team

BASE = os.path.join(os.path.dirname(__file__), "..")
CORPUS = os.path.join(BASE, "data", "real", "corpus_all.csv")
SEED = 20261004  # deterministic candidate sampling


def load_corpus() -> list[dict]:
    with open(CORPUS, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def upsert_problems(db, rows: list[dict]) -> dict:
    existing = {r.source_id: r.id for r in db.scalars(select(RealProblem)).all()}
    added = 0
    for r in rows:
        sid = r["source_id"]
        if not sid or sid in existing:
            continue
        p = RealProblem(
            source=r["source"],
            source_id=sid,
            date=r.get("date", ""),
            category=r.get("category", ""),
            title=r.get("title", "")[:255],
            text=r.get("text", ""),
            location=r.get("location", "")[:255],
            area=r.get("area", "")[:120],
            status=r.get("status", "")[:40],
            duplicate_flag=int(r.get("duplicate_flag") or 0),
        )
        db.add(p)
        added += 1
    db.commit()
    # refresh id map after commit
    for r in rows:
        if r["source_id"] not in existing:
            existing[r["source_id"]] = None
    ids = {r.source_id: r.id for r in db.scalars(select(RealProblem)).all()}
    return {"existing": len(existing), "added": added, "ids": ids}


def _street(address: str) -> str:
    """Street portion of an address (drops number/dir when distinct streets
    share a suffix) — kept simple: full normalized address string."""
    return (address or "").strip().upper()


def mine_pairs(db, ids: dict, rows: list[dict], pairs_target: int) -> dict:
    by_sid = {r["source_id"]: r for r in rows}
    existing = {
        (p.problem_a_id, p.problem_b_id): p for p in db.scalars(select(RealPair)).all()
    }

    def add(a_sid: str, b_sid: str, source: str, similarity: float | None = None):
        a, b = ids.get(a_sid), ids.get(b_sid)
        if a is None or b is None or a == b:
            return False
        key = (min(a, b), max(a, b))
        if key in existing or (key[1], key[0]) in existing:
            return False
        pair = RealPair(problem_a_id=key[0], problem_b_id=key[1],
                        similarity=similarity, source=source)
        db.add(pair)
        existing[key] = pair
        return True

    # index by (category, street address)
    buckets: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("location"):
            buckets[(r["category"], _street(r["location"]))].append(r)

    stats = {"dup_flag": 0, "same_address": 0, "negative": 0}
    per_source_cap = max(1, pairs_target // 3)

    # 1) city-flagged duplicates (Chicago's official signal)
    flagged = [r for r in rows if r.get("duplicate_flag") == "1" and r.get("location")]
    rng = random.Random(SEED)
    rng.shuffle(flagged)
    for r in flagged:
        if stats["dup_flag"] >= per_source_cap:
            break
        bucket = buckets.get((r["category"], _street(r["location"]))) or []
        others = [o for o in bucket if o["source_id"] != r["source_id"]]
        if not others:
            continue
        # closest by date (both sides real, same street + type)
        others.sort(key=lambda o: abs(
            sum(int(x or 0) for x in o["date"].split("-"))
            - sum(int(x or 0) for x in r["date"].split("-"))
        ))
        for o in others[:2]:
            if add(r["source_id"], o["source_id"], "dup_flag"):
                stats["dup_flag"] += 1
                if stats["dup_flag"] >= per_source_cap:
                    break

    # 2) same address repeats (any source), mixed or same flag
    addr_keys = [k for k, v in buckets.items() if len(v) >= 2]
    rng.shuffle(addr_keys)
    for key in addr_keys:
        if stats["same_address"] >= per_source_cap:
            break
        bucket = sorted(buckets[key], key=lambda x: x["date"])
        for i in range(len(bucket) - 1):
            if stats["same_address"] >= per_source_cap:
                break
            if add(bucket[i]["source_id"], bucket[i + 1]["source_id"], "same_address"):
                stats["same_address"] += 1

    # 3) negative candidates: same category, different street
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("location"):
            by_cat[r["category"]].append(r)
    cat_keys = [k for k, v in by_cat.items() if len(v) >= 50]
    rng.shuffle(cat_keys)
    for key in cat_keys:
        if stats["negative"] >= per_source_cap:
            break
        cat_rows = by_cat[key]
        for _ in range(per_source_cap):
            if stats["negative"] >= per_source_cap:
                break
            a, b = rng.sample(cat_rows, 2)
            if _street(a["location"]) == _street(b["location"]):
                continue
            if add(a["source_id"], b["source_id"], "negative"):
                stats["negative"] += 1

    db.commit()
    return stats


def sample_relevance(db, rows: list[dict], ids: dict, n_problems: int) -> int:
    """Sample real problems (stratified by category) and pre-create NULL
    relevance rows for every team."""
    teams = list(db.scalars(select(Team)).all())
    if not teams:
        return 0
    already = {p.problem_id for p in db.scalars(select(RealRelevance)).all()}
    rng = random.Random(SEED + 1)

    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)
    # stratified sample across categories (min 1 per category up to n_problems)
    cats = sorted(by_cat)
    rng.shuffle(cats)
    picked: list[dict] = []
    per = max(1, n_problems // len(cats))
    for c in cats:
        picked.extend(rng.sample(by_cat[c], min(per, len(by_cat[c]))))
    picked = picked[:n_problems]

    created = 0
    for r in picked:
        pid = ids.get(r["source_id"])
        if pid is None or pid in already:
            continue
        for t in teams:
            db.add(RealRelevance(problem_id=pid, team_id=t.id, relevant=None))
            created += 1
        already.add(pid)
    db.commit()
    return created


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", type=int, default=300, help="candidate pairs target (total)")
    ap.add_argument("--relevance-problems", type=int, default=60)
    args = ap.parse_args()

    if not os.path.exists(CORPUS):
        raise SystemExit(f"corpus not found at {CORPUS} — run scripts.ingest_real first")

    rows = load_corpus()
    db = SessionLocal()
    try:
        up = upsert_problems(db, rows)
        print(f"real problems: {len(up['ids'])} in DB ({up['added']} added)")
        stats = mine_pairs(db, up["ids"], rows, args.pairs)
        print(f"candidate pairs mined: {stats}")
        n_rel = sample_relevance(db, rows, up["ids"], args.relevance_problems)
        print(f"relevance grid rows created: {n_rel}")

        # summary
        from sqlalchemy import func
        pending = db.scalar(select(func.count(RealPair.id)).where(RealPair.is_duplicate.is_(None)))
        labeled = db.scalar(select(func.count(RealPair.id)).where(RealPair.is_duplicate.is_not(None)))
        rel_labeled = db.scalar(select(func.count(RealRelevance.id)).where(RealRelevance.relevant.is_not(None)))
        print(f"pairs: {pending} pending / {labeled} labeled | relevance labeled rows: {rel_labeled}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
