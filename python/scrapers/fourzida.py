"""
Fresh 4zida scraper (cards only, no detail fetch).
Parses listing data from cards with test-data="ad-search-card" on the filtered URL.
"""
from __future__ import annotations

import re
import time
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
)

DOMAIN = "https://www.4zida.rs"

TASKS = [
    {
        "name": "belgrade_apartment",
        "base_url": (
            "https://www.4zida.rs/prodaja-stanova/blok-67-belville-novi-beograd-beograd/do-500000-evra"
            "?sortiranje=najnoviji"
            "&mesto=a-blok-blok-67a-novi-beograd-beograd"
            "&mesto=blok-33-geneks-novi-beograd-beograd"
            "&mesto=blok-38-novi-beograd-beograd"
            "&mesto=blok-64-novi-beograd-beograd"
            "&mesto=blok-65-novi-beograd-beograd"
            "&mesto=blok-70-novi-beograd-beograd"
            "&vece_od=80m2"
            "&manje_od=130m2"
            "&page={page}"
        ),
        "city": "belgrade",
        "listing_type": "apartment",
    },
    {
        "name": "pancevo_house",
        "base_url": "https://www.4zida.rs/prodaja-kuca/gradske-lokacije-pancevo?sortiranje=najnoviji&page={page}",
        "city": "pancevo",
        "listing_type": "house",
    },
    {
        "name": "pancevo_land",
        "base_url": "https://www.4zida.rs/prodaja-placeva/gradske-lokacije-pancevo?sortiranje=najnoviji&page={page}",
        "city": "pancevo",
        "listing_type": "land",
    },
]

# Regex helpers
PRICE_RE = re.compile(r"([\d\.\s,]+)\s*€")
SIZE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*m[²2]", re.IGNORECASE)
FLOOR_RE = re.compile(r"(\d+)\s*/\s*(\d+)\s*sprat", re.IGNORECASE)


def parse_price(text: str) -> Optional[int]:
    m = PRICE_RE.search(text)
    if not m:
        return None
    digits = m.group(1).replace(".", "").replace(",", "").replace(" ", "")
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def parse_size(text: str) -> Optional[float]:
    m = SIZE_RE.search(text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def parse_floor(text: str) -> Optional[int]:
    m = FLOOR_RE.search(text)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    m = re.search(r"(\d+)\s*sprat", text, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def build_title(street: str, location: str, size: Optional[float], rooms: Optional[float], price: Optional[int]) -> str:
    parts = []
    if street:
        parts.append(street.strip())
    if location:
        parts.append(location.strip())
    if price is not None:
        parts.append(f"{price:,}€".replace(",", "."))
    if size is not None:
        parts.append(f"{size:g}m²")
    if rooms is not None:
        parts.append(f"{rooms:g} sobe")
    return ", ".join(parts) if parts else street or location


def block_from_url(url: str) -> Optional[str]:
    low = url.lower()
    if "blok-33" in low or "blok%2033" in low:
        return "blok-33"
    if "blok-38" in low or "blok%2038" in low:
        return "blok-38"
    if "blok-64" in low or "blok%2064" in low:
        return "blok-64"
    if "blok-65" in low or "blok%2065" in low:
        return "blok-65"
    if "blok-70" in low or "blok%2070" in low:
        return "blok-70"
    if "blok-67a" in low or "blok%2067a" in low or "a-blok" in low:
        return "blok-67"
    if "blok-67" in low or "blok%2067" in low:
        return "blok-67"
    return None


def parse_card(card, *, city: str, listing_type: str) -> Optional[Listing]:
    # Primary link
    header_link = card.select_one("a[href*='/prodaja-']")
    if not header_link or not header_link.has_attr("href"):
        return None
    href = header_link["href"]
    url = href if href.startswith("http") else DOMAIN.rstrip("/") + href

    street_el = header_link.select_one("p.truncate") or header_link.select_one("p")
    street = street_el.get_text(strip=True) if street_el else ""
    location_el = header_link.select_one("p.text-xs") or header_link.select_one("p:nth-of-type(2)")
    location = location_el.get_text(strip=True) if location_el else ""

    price_el = header_link.select_one("p.bg-spotlight") or header_link.select_one("p.font-bold")
    price_text = price_el.get_text(" ", strip=True) if price_el else card.get_text(" ", strip=True)
    price = parse_price(price_text)

    # Meta line like "101m² | 3 sobe | 4/10 spratova"
    meta_link = card.select_one("a[href*='/prodaja-stanova/']:not(:first-child)") or header_link.find_next("a")
    meta_text = meta_link.get_text(" ", strip=True) if meta_link else ""
    size = parse_size(meta_text)
    rooms = detect_rooms(meta_text) or detect_rooms(street) or detect_rooms(location)
    floor = parse_floor(meta_text)

    raw_text = card.get_text(" ", strip=True)
    block_code = block_from_url(url) or detect_block(" ".join([street, location, raw_text]))
    if not block_code and city == "pancevo":
        block_code = "pancevo"  # city-level bucket for Pancevo
    if not block_code:
        return None
    if not block_code:
        return None

    title = street or build_title(street, location, size, rooms, price)
    external_id = url.rstrip("/").split("/")[-1]

    thumb = None
    img = card.select_one("img")
    if img:
        for attr in ["data-src", "data-original", "srcset", "src"]:
            if img.has_attr(attr):
                val = img[attr]
                if attr == "srcset":
                    val = val.split(",")[0].split()[0]
                thumb = val if val.startswith("http") else DOMAIN.rstrip("/") + "/" + val.lstrip("/")
                break

    price_per_sqm = None
    if price and size:
        try:
            price_per_sqm = round(price / float(size), 2)
        except Exception:
            price_per_sqm = None

    return Listing(
        source="4zida",
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
        thumbnail_url=thumb,
        is_agency=detect_agency(raw_text),
        raw_text=raw_text,
        raw_json=None,
        source_links=None,
        is_duplicate=False,
        price_per_sqm=price_per_sqm,
        listing_date=None,
    )


def fetch_page(
    session: requests.Session,
    base_url: str,
    page: int,
    *,
    city: str,
    listing_type: str,
    task_name: str,
    min_delay: float = 1.0,
    freshness_days: int = 60,  # unused; kept for signature compatibility
) -> List[Listing]:
    resp = session.get(base_url.format(page=page), timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    cards = soup.select(
        "div[test-data='ad-search-card'], div[test-data=ad-search-card], [data-test='ad-search-card']"
    )
    if page == 1:
        print(f"[debug 4zida] task={task_name} page {page}: selected {len(cards)} cards from {resp.url}")
    results: List[Listing] = []
    for idx, card in enumerate(cards):
        item = parse_card(card, city=city, listing_type=listing_type)
        if item:
            results.append(item)
        elif page == 1 and idx == 0:
            preview = card.get_text(" ", strip=True)[:200]
            print(f"[debug 4zida] first card skipped; preview: {preview}")
        time.sleep(min_delay)
    return results


def scrape_all(
    max_pages: int = 3,
    min_delay: float = 1.0,
    freshness_days: int = 60,  # unused; kept for compatibility
) -> List[Listing]:
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
                min_delay=min_delay,
                freshness_days=freshness_days,
            )
            if not items:
                break
            all_items.extend(items)
    return all_items



