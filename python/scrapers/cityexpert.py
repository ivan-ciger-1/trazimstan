"""
CityExpert importer via public search API (cards only).
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import List, Optional

import requests

from python.scrapers.base import (
    Listing,
    RateLimiter,
    detect_block,
    detect_rooms,
    new_session,
    parse_price_eur,
    to_number,
)

SEARCH_URL = "https://cityexpert.rs/api/Search"
DETAIL_URL = "https://cityexpert.rs/api/PropertyView/{prop_id}/s"
REQ_PAYLOAD = {
    "ptId": [1],
    "cityId": 1,
    "rentOrSale": "s",
    "minSize": 80,
    "maxSize": 150,
    "searchSource": "regular",
    "sort": "datedsc",
    "polygonsArray": [
        "Blok 67 (Belville)",
        "Blok 67a (A Blok)",
        "Blok 33",
        "Blok 38",
        "Blok 64",
        "Blok 65",
        "Blok 70",
    ],
}


def block_from_polygons(polys: List[str], street: str) -> Optional[str]:
    low_polys = [p.lower() for p in polys]
    if any("blok 67" in p for p in low_polys):
        return "blok-67"
    if any("blok 67a" in p for p in low_polys) or any("(a blok)" in p for p in low_polys):
        return "blok-67"
    if any("blok 33" in p for p in low_polys):
        return "blok-33"
    if any("blok 38" in p for p in low_polys):
        return "blok-38"
    if any("blok 64" in p for p in low_polys):
        return "blok-64"
    if any("blok 65" in p for p in low_polys):
        return "blok-65"
    if any("blok 70" in p for p in low_polys):
        return "blok-70"
    return detect_block(street)


def parse_floor(floor_str: Optional[str]) -> Optional[int]:
    if not floor_str:
        return None
    m = re.match(r"(\d+)", floor_str)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _structure_slug(structure: Optional[str]) -> str:
    if not structure:
        return "stan"
    mapping = {
        "0.5": "garsonjera",
        "1.0": "jednosoban-stan",
        "1.5": "jednoiposoban-stan",
        "2.0": "dvosoban-stan",
        "2.5": "dvoiposoban-stan",
        "3.0": "trosoban-stan",
        "3.5": "troiposoban-stan",
        "4.0": "cetvorosoban-stan",
        "4.5": "cetvoroiposoban-stan",
        "5.0": "petosoban-stan",
    }
    return mapping.get(structure, "stan")


def _slugify(text: str) -> str:
    txt = text.strip().lower()
    txt = re.sub(r"[^\w\s-]", "", txt)
    txt = re.sub(r"\s+", "-", txt)
    txt = re.sub(r"-+", "-", txt)
    return txt.strip("-")


def build_ce_url(prop_id: str, structure: str, street: str) -> str:
    struct_part = _structure_slug(structure)
    street_part = _slugify(street) if street else "beograd"
    return f"https://cityexpert.rs/prodaja-nekretnina/beograd/{prop_id}/{struct_part}-{street_part}-beograd"


def build_thumb(cover: Optional[str]) -> Optional[str]:
    if not cover:
        return None
    return f"https://img.cityexpert.rs/sites/default/files/styles/470x/public/image/{cover}"


def parse_listing(item: dict) -> Optional[Listing]:
    price = int(item.get("price")) if item.get("price") is not None else None
    size = float(item.get("size")) if item.get("size") is not None else None
    rooms = detect_rooms(str(item.get("structure", ""))) or to_number(str(item.get("structure", "")))
    floor = parse_floor(item.get("floor"))
    polygons = item.get("polygons") or []
    street = item.get("street") or ""
    block_code = block_from_polygons(polygons, street)
    if not block_code:
        return None

    prop_id = str(item.get("propId") or item.get("uniqueID"))
    url = build_ce_url(prop_id, str(item.get("structure", "")), street)
    title = street or f"{item.get('location','')}"
    external_id = prop_id

    listing_date = None
    first_published = item.get("firstPublished")
    if first_published:
        try:
            listing_date = datetime.fromisoformat(first_published.replace("Z", "+00:00")).date().isoformat()
        except Exception:
            listing_date = None

    price_per_sqm = None
    if price and size:
        try:
            price_per_sqm = round(price / float(size), 2)
        except Exception:
            price_per_sqm = None

    return Listing(
        source="cityexpert",
        external_id=external_id,
        city="belgrade",
        listing_type="apartment",
        block_code=block_code,
        title=title,
        price_eur=price,
        size_m2=size,
        rooms=rooms,
        floor=floor,
        url=url,
        thumbnail_url=build_thumb(item.get("coverPhoto")),
        is_agency=False,  # cityexpert acts as direct source, treat as non-agency
        raw_text=json.dumps(item),
        raw_json=item,
        source_links=None,
        is_duplicate=False,
        price_per_sqm=price_per_sqm,
        listing_date=listing_date,
    )


def enrich_with_detail(listing: Listing, prop_id: str, session: requests.Session) -> Listing:
    """
    Fetch single-listing detail to refine fields (floor, listing_date if missing).
    """
    try:
        resp = session.get(DETAIL_URL.format(prop_id=prop_id), timeout=10)
        resp.raise_for_status()
        detail = resp.json()
    except Exception:
        return listing

    # Floor
    for key in ["floor", "floorNumber", "sprat"]:
        if detail.get(key) is not None:
            floor = to_number(str(detail.get(key)))
            if floor is not None:
                listing.floor = int(floor)
                break

    # Listing date
    if not listing.listing_date:
        for key in ["publishDate", "publishedOn", "firstPublished", "datePublished", "updatedAt"]:
            val = detail.get(key)
            if val:
                try:
                    listing.listing_date = datetime.fromisoformat(val.replace("Z", "+00:00")).date().isoformat()
                    break
                except Exception:
                    continue

    # Thumbnail
    if not listing.thumbnail_url:
        cover = detail.get("coverImage")
        if cover:
            listing.thumbnail_url = build_thumb(cover)

    # Price per sqm (recompute if needed)
    if listing.price_per_sqm is None and listing.price_eur and listing.size_m2:
        try:
            listing.price_per_sqm = round(listing.price_eur / float(listing.size_m2), 2)
        except Exception:
            listing.price_per_sqm = None

    return listing


def scrape_all(max_pages: int = 1, min_delay: float = 1.0, freshness_days: int = 60) -> List[Listing]:  # noqa: ARG001
    session = new_session()
    limiter = RateLimiter(min_delay_seconds=min_delay)
    items: List[Listing] = []
    for page in range(1, max_pages + 1):
        limiter.wait()
        payload = dict(REQ_PAYLOAD)
        payload["page"] = page
        resp = session.get(SEARCH_URL, params={"req": json.dumps(payload)}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("result") or []
        for r in results:
            listing = parse_listing(r)
            if listing:
                listing = enrich_with_detail(listing, prop_id=str(r.get("propId") or r.get("uniqueID")), session=session)
                items.append(listing)
        info = data.get("info") or {}
        if not info.get("hasNextPage"):
            break
    return items


if __name__ == "__main__":
    listings = scrape_all(max_pages=2)
    print(f"Fetched {len(listings)} listings")
    for l in listings[:5]:
        print(l)

