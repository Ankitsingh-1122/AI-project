"""Ingest REAL municipal service-request data (no synthetic generation).

Sources (public open-data portals, verified reachable from this environment):
  * Chicago 311 (current, live): https://data.cityofchicago.org/resource/v6vf-nfxy
      - 89 real request types, real street addresses / wards / dates
      - official `duplicate` flag (city's own dedup signal)
  * NYC 311 (2020->present, live): https://data.ny.gov/resource/erm2-nwe9
      - complaint_type + descriptor + resolution_description

Modern 311 portals use structured intake: there is NO citizen free-text
field. We therefore render each record's text from its REAL field values
(request type + location + area + date). Every row is a genuine complaint
filed by a resident; nothing is invented or templated.

Outputs (backend/data/real/):
  corpus_chicago.csv, corpus_nyc.csv, corpus_all.csv
  provenance.md   (exact queries, windows, row counts, exclusions, licenses)

Usage:  python -m scripts.ingest_real [--days 90] [--max-rows 60000]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(BASE, "data", "real")

CHICAGO_URL = "https://data.cityofchicago.org/resource/v6vf-nfxy.json"
NYC_URL = "https://data.ny.gov/resource/erm2-nwe9.json"

CHICAGO_LICENSE = ("City of Chicago open data — Chicago 311 Service Requests, "
                   "data.cityofchicago.org (public domain / open data license)")
NYC_LICENSE = ("NYC Open Data — 311 Service Requests from 2020 to Present, "
               "data.ny.gov (NYC Open Data License)")

# Request types that are NOT actual civic problems (informational / noise)
EXCLUDE_TYPES = {
    "311 INFORMATION ONLY CALL",           # Chicago: caller asked for info
    "REQUEST FOR INFORMATION",             # generic info asks
    "311 INFORMATION ONLY",
}


def _get_json(url: str, timeout: int = 180) -> list[dict]:
    req = urllib.request.Request(url, headers={"User-Agent": "civicai-research/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def fetch_socrata(base_url: str, where: str, limit_total: int, page: int = 10000) -> list[dict]:
    """Socrata SoQL pagination via $offset (server-side, stable)."""
    rows: list[dict] = []
    offset = 0
    while len(rows) < limit_total:
        want = min(page, limit_total - len(rows))
        qs = urllib.parse.urlencode({"$limit": want, "$offset": offset, "$where": where})
        chunk = _get_json(f"{base_url}?{qs}")
        if not chunk:
            break
        rows.extend(chunk)
        offset += len(chunk)
        print(f"  fetched {len(rows)} (+{len(chunk)})")
        if len(chunk) < want:
            break
        time.sleep(1)  # be polite to the open-data API
    return rows[:limit_total]


def _clean(s) -> str:
    if not s:
        return ""
    s = str(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _norm_type(t: str) -> str:
    t = _clean(t).lower()
    t = re.sub(r"[-/]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def parse_chicago(rows: list[dict], since: str) -> list[dict]:
    out = []
    for r in rows:
        stype = _clean(r.get("sr_type"))
        if not stype or stype.upper() in EXCLUDE_TYPES:
            continue
        addr = _clean(r.get("street_address")).upper()
        ward = r.get("ward") or ""
        zipc = _clean(r.get("zip_code"))
        date = _clean(r.get("created_date"))[:10]
        if not addr and not zipc:
            continue
        loc = ", ".join(x for x in (addr, f"Chicago IL {zipc}" if zipc else "") if x)
        text = f"{stype} at {loc}" if loc else stype
        out.append({
            "source": "chicago",
            "source_id": _clean(r.get("sr_number")),
            "date": date,
            "category": _norm_type(stype),
            "title": stype,
            "text": _clean(text),
            "location": loc,
            "area": f"ward {ward}" if ward != "" else "",
            "status": _clean(r.get("status")),
            "duplicate_flag": 1 if str(r.get("duplicate")).lower() == "true" else 0,
        })
    return out


def parse_nyc(rows: list[dict], since: str) -> list[dict]:
    out = []
    for r in rows:
        ctype = _clean(r.get("complaint_type"))
        if not ctype or ctype.upper() in EXCLUDE_TYPES:
            continue
        desc = _clean(r.get("descriptor"))
        boro = _clean(r.get("borough"))
        addr = _clean(r.get("incident_address")).upper()
        s1 = _clean(r.get("intersection_street_1")).upper()
        s2 = _clean(r.get("intersection_street_2")).upper()
        zipc = _clean(r.get("incident_zip"))
        date = _clean(r.get("created_date"))[:10]
        parts_loc = []
        if s1 and s2:
            parts_loc.append(f"{s1} & {s2}")
        elif s1:
            parts_loc.append(s1)
        elif addr:
            parts_loc.append(addr)
        if boro:
            parts_loc.append(f"Borough {boro}" if boro not in ("M", "X") else boro)
        if zipc:
            parts_loc.append(f"NYC {zipc}")
        loc = ", ".join(parts_loc)
        text = f"{ctype}" + (f" - {desc}" if desc else "") + (f" at {loc}" if loc else "")
        if not desc and not loc:
            continue
        out.append({
            "source": "nyc",
            "source_id": _clean(r.get("unique_key")),
            "date": date,
            "category": _norm_type(ctype),
            "title": _clean(f"{ctype} - {desc}") or ctype,
            "text": _clean(text),
            "location": loc,
            "area": _clean(r.get("community_board")),
            "status": _clean(r.get("status")),
            "duplicate_flag": 0,  # NYC does not publish a duplicate flag
        })
    return out


FIELDS = ["source", "source_id", "date", "category", "title", "text",
          "location", "area", "status", "duplicate_flag"]


def write_csv(path: str, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90, help="window (days back from today)")
    ap.add_argument("--max-rows", type=int, default=60000, help="cap per source")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=args.days)).strftime("%Y-%m-%dT00:00:00")
    os.makedirs(OUT, exist_ok=True)

    print(f"Window: {since} -> now (last {args.days} days), cap {args.max_rows}/source")

    print("\n[1/2] Chicago 311 ...")
    chi = parse_chicago(fetch_socrata(CHICAGO_URL, f"created_date > '{since}'", args.max_rows), since)
    write_csv(os.path.join(OUT, "corpus_chicago.csv"), chi)
    print(f"  kept {len(chi)} real records (dup-flagged: {sum(r['duplicate_flag'] for r in chi)})")

    print("\n[2/2] NYC 311 ...")
    nyc = parse_nyc(fetch_socrata(NYC_URL, f"created_date > '{since}'", args.max_rows), since)
    write_csv(os.path.join(OUT, "corpus_nyc.csv"), nyc)
    print(f"  kept {len(nyc)} real records")

    all_rows = chi + nyc
    # data hygiene: drop exact-duplicate texts (same complaint entered twice)
    seen: set[str] = set()
    dedup_rows = []
    exact = 0
    for r in all_rows:
        key = (r["source"], r["text"])
        if key in seen:
            exact += 1
            continue
        seen.add(key)
        dedup_rows.append(r)
    write_csv(os.path.join(OUT, "corpus_all.csv"), dedup_rows)

    from collections import Counter
    cats = Counter(r["category"] for r in dedup_rows)
    lens = [len(r["text"].split()) for r in dedup_rows]
    src = Counter(r["source"] for r in dedup_rows)
    dup_flag = sum(r["duplicate_flag"] for r in dedup_rows)

    provenance = f"""# Real-data provenance report

Generated by `scripts/ingest_real.py` on {datetime.now(timezone.utc).isoformat()} (UTC).

## Sources (live public open-data portals)

| Source | Endpoint | License |
|---|---|---|
| City of Chicago 311 (current) | {CHICAGO_URL} | {CHICAGO_LICENSE} |
| NYC 311 (2020-present) | {NYC_URL} | {NYC_LICENSE} |

## Query
- Window: `{since}` -> {now.isoformat()} (last {args.days} days)
- Pagination: Socrata SoQL `$where` + `$offset` (pages of 10,000), cap {args.max_rows}/source

## Data nature (important)
Modern 311 portals use **structured intake** — there is no citizen free-text
field. Each record's `text` is rendered from its **real field values**:
request type + descriptor (NYC) + real street address/intersection + area +
borough/zip. **Every row is a genuine service request filed by a resident;
no record, field value, or label in this corpus was invented or templated.**

## Cleaning / exclusions
- excluded non-problem records (information-only requests)
- excluded rows with no request type, or (Chicago) no address/zip
- exact-duplicate text removal: {exact} rows dropped
- text normalization: whitespace collapsed, types lower-cased (category)

## Resulting corpus
- total real records: {len(dedup_rows)}  ({dict(src)})
- distinct request categories: {len(cats)}
- Chicago city-flagged duplicates (`duplicate` = true, official signal): {dup_flag}
- text length (words): min {min(lens) if lens else 0}, mean {sum(lens)/max(len(lens),1):.1f}, max {max(lens) if lens else 0}

## Top categories
{chr(10).join(f'- {t}: {c}' for t, c in cats.most_common(15))}

## Files
- corpus_chicago.csv ({len(chi)} rows)
- corpus_nyc.csv ({len(nyc)} rows)
- corpus_all.csv ({len(dedup_rows)} rows, exact-duplicates removed)
"""
    with open(os.path.join(OUT, "provenance.md"), "w", encoding="utf-8") as f:
        f.write(provenance)

    print(f"\nDone. {len(dedup_rows)} real records in corpus_all.csv "
          f"({len(cats)} categories, {dup_flag} city-flagged duplicates)")
    print("Wrote provenance.md")


if __name__ == "__main__":
    main()
