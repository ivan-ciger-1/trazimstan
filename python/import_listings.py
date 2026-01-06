"""
Ingest listings from scrapers into PostgreSQL.
- Scrapes nekretnine.rs and HaloOglasi with a freshness window (default 60 days).
- Upserts on dedupe_key to merge cross-source duplicates.
"""
from __future__ import annotations

import os
import re
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import requests

import psycopg
from psycopg.rows import dict_row

from python.scrapers import halooglasi, nekretnine, fourzida, cityexpert
from python.scrapers.base import (
    Listing,
    chunk,
    normalize_title_for_dedupe,
)


def get_db_url() -> str:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is required")
    return db_url


def fetch_source_ids(conn) -> Dict[str, int]:
    rows = conn.execute("select id, name from sources").fetchall()
    return {row["name"]: row["id"] for row in rows}


def upsert_listings(conn, records: List[Dict]) -> None:
    """
    Upsert on dedupe_key (unique partial index). We also update source/external_id
    to let the newest record carry its source identity.
    """
    sql = """
    INSERT INTO listings (
      source_id, external_id, block_code, title, price_eur, size_m2, rooms, floor,
      url, thumbnail_url, is_agency, is_duplicate, price_per_sqm, listing_date,
      raw_text, raw_json, source_links, dedupe_key, last_seen_at
    )
    VALUES (
      %(source_id)s, %(external_id)s, %(block_code)s, %(title)s, %(price_eur)s,
      %(size_m2)s, %(rooms)s, %(floor)s, %(url)s, %(thumbnail_url)s, %(is_agency)s,
      %(is_duplicate)s, %(price_per_sqm)s, %(listing_date)s,
      %(raw_text)s, %(raw_json)s, %(source_links)s, %(dedupe_key)s, now()
    )
    ON CONFLICT (source_id, external_id) DO UPDATE SET
      block_code = EXCLUDED.block_code,
      title = EXCLUDED.title,
      price_eur = EXCLUDED.price_eur,
      size_m2 = EXCLUDED.size_m2,
      rooms = EXCLUDED.rooms,
      floor = EXCLUDED.floor,
      url = EXCLUDED.url,
      thumbnail_url = EXCLUDED.thumbnail_url,
      is_agency = EXCLUDED.is_agency,
      is_duplicate = EXCLUDED.is_duplicate,
      price_per_sqm = EXCLUDED.price_per_sqm,
      listing_date = EXCLUDED.listing_date,
      raw_text = EXCLUDED.raw_text,
      raw_json = EXCLUDED.raw_json,
      source_links = EXCLUDED.source_links,
      dedupe_key = EXCLUDED.dedupe_key,
      last_seen_at = now();
    """
    with conn.cursor() as cur:
        for batch in chunk(records, 200):
            # Sort so that HaloOglasi (source name 'halooglasi') rows come last,
            # therefore winning the ON CONFLICT update.
            batch_sorted = sorted(
                batch,
                key=lambda r: 0 if r.get("source_name") == "nekretnine.rs" else 1,
            )
            # Adapt source_links to JSON for psycopg.
            adapted = []
            for rec in batch_sorted:
                rec_copy = rec.copy()
                if rec_copy.get("source_links") is not None:
                    rec_copy["source_links"] = json.dumps(rec_copy["source_links"])
                if isinstance(rec_copy.get("raw_json"), (dict, list)):
                    rec_copy["raw_json"] = json.dumps(rec_copy["raw_json"])
                adapted.append(rec_copy)
            cur.executemany(sql, adapted)
    # report simple duplicate count within this batch set
    dedupes = {rec["dedupe_key"] for rec in records if rec.get("dedupe_key")}
    duplicates = len(records) - len(dedupes)
    return {"processed": len(records), "duplicates_in_batch": duplicates}


def clear_listings(conn) -> None:
    """
    Remove all rows from listings. Uses TRUNCATE CASCADE to keep FKs happy.
    """
    with conn.cursor() as cur:
        cur.execute("TRUNCATE listings RESTART IDENTITY CASCADE;")


def scrape_all(freshness_days: int = 60, max_pages: int = 3) -> List[Listing]:
    items: List[Listing] = []
    items += nekretnine.scrape_all(max_pages=max_pages, freshness_days=freshness_days)
    items += halooglasi.scrape_all(max_pages=max_pages, freshness_days=freshness_days)
    items += fourzida.scrape_all(max_pages=max_pages, freshness_days=freshness_days)
    items += cityexpert.scrape_all(max_pages=max_pages, freshness_days=freshness_days)
    return items


def prefer_newest_and_collect_links(listings: List[Listing]) -> List[Listing]:
    """
    Deduplicate in-memory by a cluster.
    - For 4zida: block + exact price + room bucket (title ignored).
    - For others: block + size bucket + price bucket + room bucket (previous logic).
    Within each cluster, first pick the best per source, then pick the overall best.
    Mark as duplicate only if more than one source remains. Collect all per-source links.
    """
    def size_bucket(sz: Optional[float]) -> Optional[float]:
        if sz is None:
            return None
        return round(sz / 1.0)  # bucket by 1 m2

    def price_bucket(price: Optional[int]) -> Optional[int]:
        if price is None:
            return None
        return int(round(price / 1000))  # bucket by 1k EUR

    def room_bucket(rooms: Optional[float]) -> Optional[float]:
        if rooms is None:
            return None
        return round(rooms * 2) / 2.0  # bucket by 0.5 rooms

    def title_tokens(norm_title: str) -> set:
        return set(norm_title.split()) if norm_title else set()

    def title_similarity(a: str, b: str) -> float:
        ta, tb = title_tokens(a), title_tokens(b)
        if not ta or not tb:
            return 0.0
        inter = len(ta & tb)
        denom = max(len(ta), len(tb))
        return inter / denom if denom else 0.0

    clusters: Dict[tuple, List[Listing]] = {}
    for l in listings:
        if l.source == "cityexpert" and l.floor is not None:
            key = (
                l.block_code,
                l.price_eur,  # exact price
                size_bucket(l.size_m2),
                l.floor,  # distinct by floor for cityexpert
            )
        else:
            key = (
                l.block_code,
                l.price_eur,  # exact price to align cross-source
                size_bucket(l.size_m2),
            )
        clusters.setdefault(key, []).append(l)

    chosen: List[Listing] = []
    for recs in clusters.values():
        is_dup = len(recs) > 1
        if len(recs) == 1:
            recs[0].source_links = [{"source": recs[0].source, "url": recs[0].url}]
            recs[0].is_duplicate = False
            if recs[0].source == "4zida" and recs[0].listing_date is None:
                recs[0].listing_date = fetch_4zida_listing_date(recs[0].url)
            if recs[0].listing_date is None:
                recs[0].listing_date = extract_date_iso(recs[0].raw_text)
            if recs[0].price_per_sqm is None and recs[0].price_eur and recs[0].size_m2:
                recs[0].price_per_sqm = round(recs[0].price_eur / recs[0].size_m2, 2)
            chosen.append(recs[0])
            continue
        # Scoring helpers.
        def parsed_date(x: Listing):
            d = extract_date(x.raw_text)
            return d if d else 0

        def completeness(x: Listing) -> int:
            return sum(
                v is not None
                for v in [x.price_eur, x.size_m2, x.rooms, x.floor, x.thumbnail_url]
            )

        # Pick best per source first.
        per_source: Dict[str, Listing] = {}
        for r in recs:
            if r.source not in per_source:
                per_source[r.source] = r
                continue
            existing = per_source[r.source]
            cand = sorted(
                [existing, r],
                key=lambda x: (parsed_date(x), completeness(x)),
                reverse=True,
            )[0]
            per_source[r.source] = cand

        per_source_list = list(per_source.values())
        per_source_list_sorted = sorted(
            per_source_list,
            key=lambda x: (parsed_date(x), completeness(x)),
            reverse=True,
        )

        # Require at least one matching attribute (rooms or size or floor) to merge.
        def shares_attr(a: Listing, b: Listing) -> bool:
            price_match = (
                a.price_eur is not None
                and b.price_eur is not None
                and a.price_eur == b.price_eur
            )
            size_match = (
                a.size_m2 is not None
                and b.size_m2 is not None
                and abs(a.size_m2 - b.size_m2) < 0.01
            )
            rooms_match = a.rooms is not None and b.rooms is not None and a.rooms == b.rooms
            floor_match = a.floor is not None and b.floor is not None and a.floor == b.floor

            # Stricter rule when cityexpert is involved: require price + size + rooms + floor (if present).
            if "cityexpert" in (a.source, b.source):
                if price_match and size_match and rooms_match:
                    if a.floor is not None and b.floor is not None:
                        return a.floor == b.floor
                    return True
                return False

            if price_match and size_match:
                return True
            if rooms_match:
                return True
            if size_match:
                return True
            if floor_match:
                return True
            return False

        has_attr_match = False
        for i in range(len(per_source_list_sorted)):
            for j in range(i + 1, len(per_source_list_sorted)):
                if shares_attr(per_source_list_sorted[i], per_source_list_sorted[j]):
                    has_attr_match = True
                    break
            if has_attr_match:
                break

        if not has_attr_match:
            for r in per_source_list_sorted:
                r.is_duplicate = False
                r.source_links = [{"source": r.source, "url": r.url}]
                if r.source == "4zida" and r.listing_date is None:
                    r.listing_date = fetch_4zida_listing_date(r.url)
                if r.price_per_sqm is None and r.price_eur and r.size_m2:
                    r.price_per_sqm = round(r.price_eur / r.size_m2, 2)
                if r.listing_date is None:
                    r.listing_date = extract_date_iso(r.raw_text)
                chosen.append(r)
            continue

        # Merge all candidates in the cluster.
        anchor = sorted(
            per_source_list_sorted,
            key=lambda x: (parsed_date(x), completeness(x)),
            reverse=True,
        )[0]
        anchor.is_duplicate = len({m.source for m in per_source_list_sorted}) > 1

        links = []
        seen_links = set()
        for r in per_source_list_sorted:
            sig = (r.source, r.url)
            if sig in seen_links:
                continue
            seen_links.add(sig)
            links.append({"source": r.source, "url": r.url})
        anchor.source_links = links

        if any(link["source"] == "cityexpert" for link in anchor.source_links):
            anchor.is_agency = False

        if anchor.price_per_sqm is None and anchor.price_eur and anchor.size_m2:
            anchor.price_per_sqm = round(anchor.price_eur / anchor.size_m2, 2)
        if anchor.source == "4zida" and anchor.listing_date is None:
            anchor.listing_date = fetch_4zida_listing_date(anchor.url)
        if anchor.listing_date is None:
            anchor.listing_date = extract_date_iso(anchor.raw_text)
        chosen.append(anchor)
    return chosen


DATE_RE = re.compile(r"(\d{2}\.\d{2}\.\d{4})")
RELATIVE_RE = re.compile(r"pre\s+(\d+)\s+dan", re.IGNORECASE)
ABSOLUTE_DATE_RE = re.compile(r"(\d{2}\.\d{2}\.\d{4})")


def extract_date(text: str) -> Optional[int]:
    """
    Extract a date (dd.mm.yyyy) and return an int timestamp for ordering.
    """
    m = DATE_RE.search(text)
    if not m:
        return None
    try:
        dt = datetime.strptime(m.group(1), "%d.%m.%Y")
        return int(dt.timestamp())
    except ValueError:
        return None


def extract_date_iso(text: str) -> Optional[str]:
    ts = extract_date(text)
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, timezone.utc).date().isoformat()


def extract_relative_date_iso(text: str) -> Optional[str]:
    """
    Parse relative dates like 'pre 2 dana' from 4zida detail pages.
    """
    m = RELATIVE_RE.search(text)
    if not m:
        m_abs = ABSOLUTE_DATE_RE.search(text)
        if m_abs:
            try:
                dt = datetime.strptime(m_abs.group(1), "%d.%m.%Y").date()
                return dt.isoformat()
            except ValueError:
                return None
        return None
    try:
        days = int(m.group(1))
    except ValueError:
        return None
    dt = datetime.utcnow().date() - timedelta(days=days)
    return dt.isoformat()


def find_duplicate_sample(listings: List[Listing]) -> Optional[Dict]:
    """
    Return one example duplicate (same dedupe_key) with two entries from possibly
    different sources so we can log it.
    """
    bucket: Dict[str, List[Listing]] = {}
    for l in listings:
        bucket.setdefault(l.dedupe_key, []).append(l)
    for k, recs in bucket.items():
        if len(recs) > 1:
            # Prefer showing two different sources if available.
            if len({r.source for r in recs}) > 1:
                a = recs[0]
                b = next(r for r in recs if r.source != a.source)
            else:
                a, b = recs[0], recs[1]
            return {
                "dedupe_key": k,
                "count": len(recs),
                "items": [
                    {"source": a.source, "title": a.title, "url": a.url},
                    {"source": b.source, "title": b.title, "url": b.url},
                ],
            }
    return None


def find_all_duplicates(listings: List[Listing]) -> List[Dict]:
    """
    Return all duplicate groups with their source links, after consolidating best per source.
    """
    bucket: Dict[str, List[Listing]] = {}
    for l in listings:
        bucket.setdefault(l.dedupe_key, []).append(l)
    results: List[Dict] = []
    for k, recs in bucket.items():
        if len(recs) <= 1:
            continue
        # Consolidate best per source.
        per_source: Dict[str, Listing] = {}
        for r in recs:
            if r.source not in per_source:
                per_source[r.source] = r
                continue
            # Keep newest per source.
            def pd(x: Listing):
                d = extract_date(x.raw_text)
                return d if d else 0

            def comp(x: Listing) -> int:
                return sum(
                    v is not None
                    for v in [x.price_eur, x.size_m2, x.rooms, x.floor, x.thumbnail_url]
                )

            per_source[r.source] = sorted(
                [per_source[r.source], r],
                key=lambda x: (pd(x), comp(x)),
                reverse=True,
            )[0]

        per_source_list = list(per_source.values())
        if len(per_source_list) <= 1:
            continue
        links = []
        seen = set()
        for r in per_source_list:
            sig = (r.source, r.url)
            if sig in seen:
                continue
            seen.add(sig)
            links.append({"source": r.source, "title": r.title, "url": r.url})
        results.append({"dedupe_key": k, "count": len(per_source_list), "links": links})
    return results


def fetch_4zida_listing_date(url: str) -> Optional[str]:
    """
    Fetch a 4zida detail page to extract listing_date (absolute or relative).
    """
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception:
        return None
    text = resp.text
    return extract_relative_date_iso(text)


def find_single_source_clusters(listings: List[Listing]) -> List[Dict]:
    """
    Return clusters where multiple records map to the same dedupe_key but only one source remains.
    Useful to inspect over-aggressive clustering.
    """
    bucket: Dict[str, List[Listing]] = {}
    for l in listings:
        bucket.setdefault(l.dedupe_key, []).append(l)
    results: List[Dict] = []
    for k, recs in bucket.items():
        if len(recs) <= 1:
            continue
        sources = {r.source for r in recs}
        if len(sources) != 1:
            continue
        links = []
        seen = set()
        for r in recs:
            sig = (r.source, r.url)
            if sig in seen:
                continue
            seen.add(sig)
            links.append({"source": r.source, "title": r.title, "url": r.url})
        results.append({"dedupe_key": k, "count": len(recs), "links": links})
    return results


def main(freshness_days: int = 60, max_pages: int = 3, clear_before: bool = False) -> None:
    db_url = get_db_url()

    # Scrape before opening DB connection to avoid idle disconnects.
    listings = scrape_all(freshness_days=freshness_days, max_pages=max_pages)
    print(f"Scraped {len(listings)} listings")
    dupes = find_all_duplicates(listings)
    single_source_dupes = find_single_source_clusters(listings)
    listings = prefer_newest_and_collect_links(listings)

    if not listings:
        print("No listings to process")
        return

    with psycopg.connect(
        db_url,
        row_factory=dict_row,
        autocommit=True,
        connect_timeout=10,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
    ) as conn:
        env_clear = os.getenv("CLEAR_LISTINGS", "1").lower() in ("1", "true", "yes")
        if clear_before or env_clear:
            print("Clearing listings table before import (TRUNCATE CASCADE)...")
            clear_listings(conn)

        source_ids = fetch_source_ids(conn)

        records = []
        for l in listings:
            sid = source_ids.get(l.source)
            if sid is None:
                print(f"[warn] source_id missing for {l.source}, skipping")
                continue
            if l.price_per_sqm is None and l.price_eur and l.size_m2:
                l.price_per_sqm = round(l.price_eur / l.size_m2, 2)
            rec = l.to_record(sid)
            rec["source_name"] = l.source  # keep name for priority sorting
            records.append(rec)

        if not records:
            print("No records to upsert")
            return

        stats = upsert_listings(conn, records)
        print(
            f"Upserted {stats['processed']} records "
            f"(duplicates within this run: {stats['duplicates_in_batch']})"
        )
        if dupes:
            print(f"Duplicate groups: {len(dupes)}")
            for d in dupes:
                links = " | ".join([f"{i['source']} -> {i['url']}" for i in d["links"]])
                print(f"dedupe_key={d['dedupe_key']}, count={d['count']}, links: {links}")
        if single_source_dupes:
            print(f"Single-source clustered groups (review): {len(single_source_dupes)}")
            for d in single_source_dupes:
                links = " | ".join([f"{i['source']} -> {i['url']}" for i in d["links"]])
                print(f"[single-source] dedupe_key={d['dedupe_key']}, count={d['count']}, links: {links}")


if __name__ == "__main__":
    main()

