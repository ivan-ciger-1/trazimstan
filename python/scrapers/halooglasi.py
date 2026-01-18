"""
Scraper for HaloOglasi real-estate (stanovi prodaja, Novi Beograd).
Reuses the same patterns as nekretnine.rs: requests + BeautifulSoup,
block detection via aliases, freshness filter (default 60 days).
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from python.scrapers.base import (
    Listing,
    RateLimiter,
    detect_agency,
    detect_block,
    detect_rooms,
    new_session,
    parse_price_eur,
    to_number,
)


DOMAIN = "https://www.halooglasi.com"

TASKS = [
    {
        "name": "belgrade_apartment",
        "base_url": "https://www.halooglasi.com/nekretnine/prodaja-stanova?grad_id_l-lokacija_id_l-mikrolokacija_id_l=52170%2C52176%2C52192%2C537331&kvadratura_d_from=80&kvadratura_d_to=150&kvadratura_d_unit=1&broj_soba_order_i_from=7&page={page}",
        "city": "belgrade",
        "listing_type": "apartment",
    },
    {
        "name": "pancevo_house",
        "base_url": "https://www.halooglasi.com/nekretnine/prodaja-kuca/pancevo?cena_d_to=250000&cena_d_unit=4&page={page}",
        "city": "pancevo",
        "listing_type": "house",
    },
    {
        "name": "pancevo_land",
        "base_url": "https://www.halooglasi.com/nekretnine/prodaja-zemljista?grad_id_l-lokacija_id_l-mikrolokacija_id_l=40487%2C58151&cena_d_to=200000&cena_d_unit=4&page={page}",
        "city": "pancevo",
        "listing_type": "land",
    },
]


def normalize_url(url: str) -> str:
    if url.startswith("http"):
        return url
    if url.startswith("//"):
        return "https:" + url
    return DOMAIN.rstrip("/") + "/" + url.lstrip("/")


def block_from_url(url: str) -> Optional[str]:
    """
    Infer block from URL slug to avoid noisy menu text.
    """
    low = url.lower()
    if "blok-33" in low or "blok%2033" in low:
        return "blok-33"
    if "blok-38" in low or "blok%2038" in low:
        return "blok-38"
    if "blok-67a" in low or "blok%2067a" in low or "a-blok" in low:
        return "blok-67"
    if "blok-67" in low or "blok%2067" in low:
        return "blok-67"
    return None


DATE_RE = re.compile(r"(\d{2}\.\d{2}\.\d{4})")


def is_recent(text: str, days: int = 60) -> bool:
    m = DATE_RE.search(text)
    if not m:
        return True
    try:
        dt = datetime.strptime(m.group(1), "%d.%m.%Y").date()
    except ValueError:
        return True
    cutoff = datetime.utcnow().date() - timedelta(days=days)
    return dt >= cutoff


def parse_price_from_text(text: str) -> Optional[int]:
    m = re.search(r"([\d\.\s,]+)\s*€", text)
    if not m:
        return None
    digits = m.group(1).replace(".", "").replace(",", "").replace(" ", "")
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def parse_size_from_text(text: str) -> Optional[float]:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*m\s*2", text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


ROMAN_MAP = {
    "i": 1,
    "ii": 2,
    "iii": 3,
    "iv": 4,
    "v": 5,
    "vi": 6,
    "vii": 7,
    "viii": 8,
    "ix": 9,
    "x": 10,
    "xi": 11,
    "xii": 12,
    "xiii": 13,
    "xiv": 14,
    "xv": 15,
}


def _roman_to_int(token: str) -> Optional[int]:
    return ROMAN_MAP.get(token.lower())


def parse_floor(text: str) -> Optional[int]:
    """
    Extract floor from patterns like 'VII/13', '3/6', or 'III/30'.
    """
    m = re.search(r"([IVXivx]+|\d+)\s*/\s*(\d+)", text)
    if m:
        floor_token = m.group(1)
        try:
            floor_val = int(floor_token)
        except ValueError:
            floor_val = _roman_to_int(floor_token)
        return floor_val
    # Sometimes floor is a single number with 'Sprat' nearby.
    m = re.search(r"(\d+)\s*sprat", text, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def parse_listing_card(card, *, city: str, listing_type: str, freshness_days: int = 60) -> Optional[Listing]:
    # HaloOglasi cards often use data-product-id on article or div.
    title_el = card.select_one(".product-title, h3 a, h4 a")
    url_el = card.select_one("a[href*='/nekretnine/prodaja-']")
    price_el = card.select_one(".central-feature .price, .price, .price-item")
    meta_el = card.select_one(".subtitle, .property-features, .central-feature")
    size_el = card.select_one(".central-feature .value, .item-info .value")
    image_el = card.select_one("img")

    title = title_el.get_text(strip=True) if title_el else ""
    url = url_el["href"] if url_el and url_el.has_attr("href") else None
    if not url:
        return None
    url = normalize_url(url)

    raw_text = card.get_text(" ", strip=True)
    meta_text = meta_el.get_text(" ", strip=True) if meta_el else raw_text

    # Block detection: first from URL, then from text to avoid menu noise.
    block_code = block_from_url(url) or detect_block(" ".join([title, meta_text, raw_text]))
    if not block_code and city == "pancevo":
        block_code = "pancevo"  # city-level bucket for Pancevo
    if not block_code:
        return None

    # Freshness filter.
    if not is_recent(raw_text, days=freshness_days):
        return None

    # Price / size / rooms / floor with fallbacks to raw text.
    price = parse_price_eur(price_el.get_text(" ", strip=True) if price_el else "") or parse_price_from_text(
        raw_text
    )
    size = to_number(size_el.get_text() if size_el else None) or parse_size_from_text(raw_text)
    rooms = detect_rooms(meta_text) or detect_rooms(title) or detect_rooms(raw_text)
    floor = parse_floor(raw_text)
    thumbnail_url = None
    if image_el:
        for attr in ["data-src", "data-original", "srcset", "src"]:
            if image_el.has_attr(attr):
                val = image_el[attr]
                if attr == "srcset":
                    # Take the first candidate in srcset.
                    val = val.split(",")[0].split()[0]
                if val:
                    thumbnail_url = normalize_url(val)
                    break

    external_id = url.rstrip("/").split("/")[-1]

    return Listing(
        source="halooglasi",
        external_id=external_id,
        city=city,
        listing_type=listing_type,
        block_code=block_code,
        title=title,
        price_eur=price,
        size_m2=size,
        rooms=rooms,
        floor=floor,
        url=url,
        thumbnail_url=thumbnail_url,
        is_agency=detect_agency(raw_text),
        raw_text=raw_text,
        raw_json=None,
    )


def fetch_page(
    session: requests.Session,
    base_url: str,
    page: int,
    *,
    city: str,
    listing_type: str,
    task_name: str,
    freshness_days: int = 60,
) -> List[Listing]:
    resp = session.get(base_url.format(page=page), timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    cards = soup.select("article[data-product-id], .product-list article, .product-item")
    if page == 1:
        print(f"[debug halooglasi] task={task_name} page {page}: selected {len(cards)} cards from {resp.url}")
    if not cards:
        snippet = soup.get_text(" ", strip=True)[:200]
        print(f"[debug halooglasi] task={task_name} page {page}: no cards; snippet: {snippet}")
    results: List[Listing] = []
    for idx, card in enumerate(cards):
        item = parse_listing_card(card, city=city, listing_type=listing_type, freshness_days=freshness_days)
        if item:
            results.append(item)
        elif page == 1 and idx == 0:
            preview = card.get_text(" ", strip=True)[:300]
            print(f"[debug halooglasi] first card skipped; preview: {preview}")
    return results


def scrape_all(max_pages: int = 3, min_delay: float = 1.0, freshness_days: int = 60) -> List[Listing]:
    session = new_session()
    limiter = RateLimiter(min_delay_seconds=min_delay)

    all_items: List[Listing] = []
    for task in TASKS:
        for page in range(1, max_pages + 1):
            limiter.wait()
            items = fetch_page(
                session,
                task["base_url"],
                page,
                city=task["city"],
                listing_type=task["listing_type"],
                task_name=task["name"],
                freshness_days=freshness_days,
            )
            if not items:
                break
            all_items.extend(items)
            time.sleep(min_delay)
    return all_items


if __name__ == "__main__":
    listings = scrape_all(max_pages=3, freshness_days=60)
    print(f"Fetched {len(listings)} listings")
    # for item in listings[:5]:
    #     print(item)

