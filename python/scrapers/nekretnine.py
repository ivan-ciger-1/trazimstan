"""
First-pass scraper for nekretnine.rs using requests + BeautifulSoup.
Focus: collect listings for Novi Beograd, detect blocks via aliases, and emit
normalized Listing objects.
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
    tasks_for_import,
    to_number,
)

DOMAIN = "https://www.nekretnine.rs"

TASKS = [
    {
        "name": "belgrade_apartment",
        "base_url": "https://www.nekretnine.rs/stambeni-objekti/stanovi/izdavanje-prodaja/prodaja/tip-stanovi/trosoban-stan_cetvorosoban-stan_petosoban-stan/deo-grada/novi-beograd-blok-33-genex-kula_novi-beograd-blok-38-os-ratko-mitrovic_novi-beograd-blok-64_novi-beograd-blok-65_novi-beograd-blok-67-belvil_novi-beograd-blok-67a_novi-beograd-blok-70-kineski-tc/grad/beograd/kvadratura/80_200/cena/1_5000000/ukupan-broj-soba/3_6/lista/po-stranici/10/",
        "city": "belgrade",
        "listing_type": "apartment",
    },
    {
        "name": "pancevo_house",
        "base_url": "https://www.nekretnine.rs/stambeni-objekti/kuce/izdavanje-prodaja/prodaja/grad/pancevo/lista/po-stranici/10/?order=2",
        "city": "pancevo",
        "listing_type": "house",
    },
    {
        "name": "pancevo_land",
        "base_url": "https://www.nekretnine.rs/zemljista/izdavanje-prodaja/prodaja/grad/pancevo/lista/po-stranici/10/?order=2",
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


DATE_RE = re.compile(r"(\d{2}\.\d{2}\.\d{4})")


def is_recent(text: str, days: int = 60) -> bool:
    """
    Accept listing if date is within the last `days`. If no date is found,
    keep the listing (fail-open).
    """
    m = DATE_RE.search(text)
    if not m:
        return True
    try:
        dt = datetime.strptime(m.group(1), "%d.%m.%Y").date()
    except ValueError:
        return True
    cutoff = datetime.utcnow().date() - timedelta(days=days)
    return dt >= cutoff


def parse_listing_card(card, *, city: str, listing_type: str, freshness_days: int = 60) -> Optional[Listing]:
    """
    Extract listing info from a single search-result card.
    We keep parsing defensive: if required fields are missing, skip the card.
    """
    # Be flexible: site classes change. Try multiple selectors for each field.
    title_el = card.select_one(".offer-title, .title, h2 a, .offer-title a")
    price_el = card.select_one(".offer-price, .price, .price-info")
    size_el = card.select_one(".offer-size, .surface, .square, .kvadratura, .offer-price--invert span")
    rooms_el = card.select_one(".offer-rooms, .rooms, .detail-rooms")
    # Links on nekretnine.rs are inside the title; include general anchors containing /stanovi/.
    url_el = card.select_one(
        "a.offer-link, .offer-title a, h2.offer-title a, a[href*='/oglas/'], "
        "a[href*='/stanovi/'], a[href*='/kuce/'], a[href*='/zemljista/']"
    )
    image_el = card.select_one("img")

    title = title_el.get_text(strip=True) if title_el else ""
    url = url_el["href"] if url_el and url_el.has_attr("href") else None
    if not url:
        return None

    url = normalize_url(url)

    # raw_text helps with later debugging and block detection.
    raw_text = card.get_text(" ", strip=True)
    block_code = detect_block(" ".join([title, raw_text]))
    if not block_code and city == "pancevo":
        block_code = "pancevo"  # city-level bucket for Pancevo
    if not block_code:
        return None  # skip non-target blocks early
    price = parse_price_eur(price_el.get_text(" ", strip=True) if price_el else "")
    size = to_number(size_el.get_text()) if size_el else None

    meta_el = card.select_one(".offer-meta-info, .offer-meta")
    meta_text = meta_el.get_text(" ", strip=True) if meta_el else raw_text
    rooms = detect_rooms(meta_text) or (detect_rooms(title) if title else None)
    thumbnail_url = None
    if image_el:
        for attr in ["data-src", "data-original", "srcset", "src"]:
            if image_el.has_attr(attr):
                val = image_el[attr]
                if attr == "srcset":
                    val = val.split(",")[0].split()[0]
                if val:
                    thumbnail_url = normalize_url(val)
                    break

    # Drop listings older than the freshness window.
    if not is_recent(meta_text, days=freshness_days):
        return None

    # nekretnine.rs URLs often end with an ID segment separated by dashes.
    external_id = url.rstrip("/").split("/")[-1]  # ID is last path segment

    return Listing(
        source="nekretnine.rs",
        external_id=external_id,
        city=city,
        listing_type=listing_type,
        block_code=block_code,
        title=title,
        price_eur=price,
        size_m2=size,
        rooms=rooms,
        floor=None,  # requires detail page; add later
        url=url,
        thumbnail_url=thumbnail_url,
        is_agency=detect_agency(raw_text),
        raw_text=raw_text,
        raw_json=None,
    )


def page_url(base_url: str, page: int) -> str:
    """
    Build the URL for a given page. Page 1 is the base; subsequent pages append
    /strana/{page}/ which is how nekretnine.rs currently paginates.
    """
    if page <= 1:
        return base_url
    return base_url.rstrip("/") + f"/strana/{page}/"


def fetch_page(
    session: requests.Session,
    base_url: str,
    page: int,
    *,
    city: str,
    listing_type: str,
    task_name: str,
    freshness_days: int = 60,
    max_retries: int = 2,
    retry_delay: float = 3.0,
) -> List[Listing]:
    """
    Fetch a single page and parse all cards. Stop early if markup changes
    (Zero cards likely means we've reached the end).
    """
    for attempt in range(1, max_retries + 1):
        try:
            resp = session.get(page_url(base_url, page), timeout=15)
            resp.raise_for_status()
            break
        except requests.exceptions.RequestException as exc:
            print(
                f"[warn nekretnine] task={task_name} page {page}: attempt {attempt}/{max_retries} failed "
                f"({exc.__class__.__name__}: {exc})"
            )
            if attempt == max_retries:
                print(
                    f"[warn nekretnine] task={task_name} page {page}: "
                    "exhausted retries, returning 0 cards for this page"
                )
                return []
            time.sleep(retry_delay)
    else:
        # Should not happen because loop returns on failure.
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    cards = soup.select(
        "article[data-id], .advert-list article, .offer, .list-item, article.offer, "
        "div.offer, div[data-id], div[data-ad-id]"
    )
    if page == 1:
        print(f"[debug nekretnine] task={task_name} page {page}: selected {len(cards)} cards from {resp.url}")
    if not cards:
        # Print small hints to adjust selectors when the site changes.
        print(f"[debug] page {page}: status {resp.status_code} url {resp.url}")
        snippet = soup.get_text(" ", strip=True)[:200]
        print(f"[debug] page {page}: no cards found; snippet: {snippet}")
        if page == 1:
            with open("debug_nekretnine_page1.html", "w", encoding="utf-8") as f:
                f.write(resp.text)
    results: List[Listing] = []
    for idx, card in enumerate(cards):
        item = parse_listing_card(card, city=city, listing_type=listing_type, freshness_days=freshness_days)
        if item:
            results.append(item)
        elif page == 1 and idx == 0:
            # If the first card fails detection, dump a preview to help adjust selectors/aliases.
            preview = card.get_text(" ", strip=True)[:300]
            print(f"[debug nekretnine] task={task_name} page {page}: first card skipped; preview: {preview}")
    if page == 1 and not results and cards:
        # Write page HTML when cards exist but nothing matched filters.
        with open("debug_nekretnine_page1.html", "w", encoding="utf-8") as f:
            f.write(resp.text)
    return results


def scrape_all(max_pages: int = 3, min_delay: float = 1.0, freshness_days: int = 60) -> List[Listing]:
    """
    Crawl a handful of pages. We stop if a page returns zero parsed listings,
    assuming we've reached the end (or the selectors broke).
    """
    session = new_session()
    limiter = RateLimiter(min_delay_seconds=min_delay)

    all_items: List[Listing] = []
    for task in tasks_for_import(TASKS):
        for page in range(1, max_pages + 1):
            limiter.wait()  # be polite between page fetches
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
            # Small pause after each page so we never hammer the site.
            time.sleep(min_delay)
    return all_items


if __name__ == "__main__":
    listings = scrape_all(max_pages=2)
    print(f"Fetched {len(listings)} listings")
    # Print a couple examples for quick eyeballing.
    # for item in listings[:3]:
    #     print(item)

