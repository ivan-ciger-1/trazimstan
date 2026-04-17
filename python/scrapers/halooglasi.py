"""
Scraper for HaloOglasi real-estate (stanovi prodaja, Novi Beograd).
Reuses the same patterns as nekretnine.rs: requests + BeautifulSoup,
block detection via aliases, freshness filter (default 60 days).
"""
from __future__ import annotations

import os
import re
import time
import urllib.error
from datetime import datetime, timedelta
from typing import Any, List, Optional, Tuple

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


DOMAIN = "https://www.halooglasi.com"

# With curl_cffi impersonation, do not set Sec-* / UA — mismatched Client Hints vs TLS
# fingerprint triggers Cloudflare blocks (common on GitHub Actions IPs).
_HALOOGLASI_HEADERS_CFFI = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "sr-RS,sr;q=0.9,en-US;q=0.8,en;q=0.7",
}

# Plain requests fallback: add Referer and a typical browser bundle.
_HALOOGLASI_HEADERS_REQUESTS = {
    **_HALOOGLASI_HEADERS_CFFI,
    "Referer": f"{DOMAIN}/",
    "Upgrade-Insecure-Requests": "1",
}


def _apply_halooglasi_headers_requests(session: Any) -> None:
    session.headers.update(_HALOOGLASI_HEADERS_REQUESTS)


def _apply_halooglasi_headers_cffi(session: Any) -> None:
    session.headers.update(_HALOOGLASI_HEADERS_CFFI)


def _cffi_impersonation_candidates() -> List[str]:
    """
    Order matters: try newer Chrome first. Override with comma-separated
    HALOOGLASI_CF_IMPERSONATE (e.g. chrome131,chrome124,safari17_0).
    """
    raw = (os.getenv("HALOOGLASI_CF_IMPERSONATE") or "").strip()
    if raw:
        parts = [x.strip() for x in raw.split(",") if x.strip()]
        if parts:
            return parts
    return ["chrome131", "chrome124", "chrome120", "edge101", "safari17_0"]


def _halooglasi_transport() -> Tuple[Any, bool]:
    """
    HaloOglasi sits behind Cloudflare; plain requests often get 403 from datacenter IPs.
    Prefer curl_cffi browser impersonation when available. Force legacy requests with
    HALOOGLASI_USE_REQUESTS=1.
    """
    if os.getenv("HALOOGLASI_USE_REQUESTS", "").strip().lower() in ("1", "true", "yes"):
        return new_session(), False
    try:
        from curl_cffi import requests as cf_requests  # type: ignore[import-untyped]

        return cf_requests.Session(), True
    except ImportError:
        return new_session(), False


def _halooglasi_get_single(
    session: Any,
    url: str,
    *,
    use_curl_cffi: bool,
    impersonate: Optional[str] = None,
) -> Any:
    timeout = 25
    ref = {"Referer": f"{DOMAIN}/"}
    if use_curl_cffi:
        imp = (impersonate or _cffi_impersonation_candidates()[0]).strip()
        return session.get(url, timeout=timeout, impersonate=imp, headers=ref)
    return session.get(url, timeout=timeout, headers=ref)


def _halooglasi_get(
    session: Any,
    url: str,
    *,
    use_curl_cffi: bool,
    impersonate: Optional[str] = None,
) -> Any:
    """
    GET with bounded retries on 403/429 only (Cloudflare / rate limits from datacenter IPs).
    HALOOGLASI_HTTP_RETRIES (default 3), HALOOGLASI_RETRY_BACKOFF_SEC (default 1.0).
    """
    raw = os.getenv("HALOOGLASI_HTTP_RETRIES", "3") or "3"
    try:
        max_attempts = int(raw)
    except ValueError:
        max_attempts = 3
    max_attempts = max(1, min(max_attempts, 5))
    try:
        base_sleep = float(os.getenv("HALOOGLASI_RETRY_BACKOFF_SEC", "1.0") or "1.0")
    except ValueError:
        base_sleep = 1.0

    last: Any = None
    for attempt in range(max_attempts):
        last = _halooglasi_get_single(
            session, url, use_curl_cffi=use_curl_cffi, impersonate=impersonate
        )
        code = getattr(last, "status_code", None)
        if code not in (403, 429):
            return last
        if attempt < max_attempts - 1:
            time.sleep(base_sleep * (attempt + 1))
    return last


def _halooglasi_warmup(
    session: Any,
    *,
    use_curl_cffi: bool,
    impersonate: Optional[str] = None,
) -> None:
    """Optional first hit to the homepage so listing requests look like in-site navigation."""
    if os.getenv("HALOOGLASI_SKIP_WARMUP", "").strip().lower() in ("1", "true", "yes"):
        return
    home = f"{DOMAIN}/"
    try:
        resp = _halooglasi_get(session, home, use_curl_cffi=use_curl_cffi, impersonate=impersonate)
        resp.raise_for_status()
    except (requests.HTTPError, urllib.error.HTTPError, requests.RequestException, OSError):
        # Warm-up is best-effort; listing fetches still run.
        pass
    try:
        delay = float(os.getenv("HALOOGLASI_WARMUP_DELAY_SEC", "0.35") or "0.35")
    except ValueError:
        delay = 0.35
    if delay > 0:
        time.sleep(delay)


TASKS = [
    {
        "name": "belgrade_apartment",
        "base_url": "https://www.halooglasi.com/nekretnine/prodaja-stanova?grad_id_l-lokacija_id_l-mikrolokacija_id_l=52176%2C52170%2C52190%2C52191%2C52192%2C52195%2C537331&cena_d_to=500000&kvadratura_d_from=80&kvadratura_d_to=150&kvadratura_d_unit=1&broj_soba_order_i_from=7&page={page}",
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


def _html_looks_like_results(html: str) -> bool:
    """Heuristic: real listing HTML vs Cloudflare interstitial / block page."""
    if not html or len(html) < 500:
        return False
    low = html.lower()
    if "just a moment" in low or "attention required" in low:
        return False
    if "cf-browser-verification" in low and len(html) < 8000:
        return False
    if "data-product-id" in html or "product-item" in low or "product-title" in low:
        return True
    return len(html) >= 12000


def _probe_cffi_session() -> Tuple[Any, str]:
    """
    Datacenter IPs often need the right browser profile; try several fresh sessions
    against the first Belgrade listing URL until HTML looks like real results.
    """
    from curl_cffi import requests as cf_requests  # type: ignore[import-untyped]

    candidates = _cffi_impersonation_candidates()
    probe_url = f"{DOMAIN}/"
    for t in tasks_for_import(TASKS):
        if t.get("city") == "belgrade":
            probe_url = t["base_url"].format(page=1)
            break

    last_sess: Any = None
    picked = candidates[0]
    for imp in candidates:
        s = cf_requests.Session()
        _apply_halooglasi_headers_cffi(s)
        try:
            r = s.get(
                probe_url,
                timeout=28,
                impersonate=imp,
                headers={"Referer": f"{DOMAIN}/"},
            )
        except Exception as exc:
            print(f"[debug halooglasi] probe impersonate={imp} error: {exc}", flush=True)
            continue
        last_sess = s
        code = getattr(r, "status_code", None)
        body = r.text or ""
        print(
            f"[debug halooglasi] probe impersonate={imp} status={code} bytes={len(body)}",
            flush=True,
        )
        if code == 200 and _html_looks_like_results(body):
            print(f"[info halooglasi] using impersonate={imp} (probe OK)", flush=True)
            return s, imp
        picked = imp

    if last_sess is not None:
        print(
            f"[warn halooglasi] probe did not confirm listing HTML; continuing with impersonate={picked}",
            flush=True,
        )
        return last_sess, picked

    s = cf_requests.Session()
    _apply_halooglasi_headers_cffi(s)
    return s, candidates[0]


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
    session: Any,
    base_url: str,
    page: int,
    *,
    city: str,
    listing_type: str,
    task_name: str,
    freshness_days: int = 60,
    use_curl_cffi: bool = False,
    impersonate: Optional[str] = None,
) -> List[Listing]:
    url = base_url.format(page=page)
    try:
        resp = _halooglasi_get(session, url, use_curl_cffi=use_curl_cffi, impersonate=impersonate)
        resp.raise_for_status()
    except requests.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else "?"
        fail_url = exc.response.url if exc.response is not None else url
        print(f"[warn halooglasi] HTTP {code} task={task_name} page={page} url={fail_url}")
        return []
    except urllib.error.HTTPError as exc:
        # curl_cffi can surface urllib HTTP errors; they subclass OSError, so handle before OSError.
        print(f"[warn halooglasi] HTTP {exc.code} task={task_name} page={page} url={url}")
        return []
    except requests.RequestException as exc:
        print(f"[warn halooglasi] request failed task={task_name} page={page}: {exc}")
        return []
    except OSError as exc:
        # curl_cffi sometimes surfaces 403 as OSError("HTTP Error 403: ..."), not HTTPError.
        es = str(exc).lower()
        if "403" in es or "401" in es or "forbidden" in es:
            print(f"[warn halooglasi] HTTP blocked task={task_name} page={page} url={url} ({exc})")
            return []
        print(f"[warn halooglasi] transport error task={task_name} page={page}: {exc}")
        return []
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
    session, use_curl_cffi = _halooglasi_transport()
    cf_impersonate: Optional[str] = None
    if use_curl_cffi:
        session, cf_impersonate = _probe_cffi_session()
    else:
        _apply_halooglasi_headers_requests(session)
    print(
        f"[info halooglasi] transport={'curl_cffi (browser TLS)' if use_curl_cffi else 'requests (may 403 behind Cloudflare)'}",
        flush=True,
    )
    _halooglasi_warmup(session, use_curl_cffi=use_curl_cffi, impersonate=cf_impersonate)
    limiter = RateLimiter(min_delay_seconds=min_delay)

    all_items: List[Listing] = []
    for task in tasks_for_import(TASKS):
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
                use_curl_cffi=use_curl_cffi,
                impersonate=cf_impersonate,
            )
            if not items:
                break
            all_items.extend(items)
            time.sleep(min_delay)
    print(f"[info halooglasi] scraped {len(all_items)} listing rows", flush=True)
    return all_items


if __name__ == "__main__":
    listings = scrape_all(max_pages=3, freshness_days=60)
    print(f"Fetched {len(listings)} listings")
    # for item in listings[:5]:
    #     print(item)

