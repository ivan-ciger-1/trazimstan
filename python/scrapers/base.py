"""
Shared helpers for scrapers: block detection, polite HTTP session, and timing.
"""
from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from typing import Dict, Iterable, Optional, List

import requests

from python.block_aliases import BLOCK_ALIASES


def new_session() -> requests.Session:
    """
    Create a requests session with a friendly User-Agent.
    Using a session reuses TCP connections, which is nicer for servers.
    """
    sess = requests.Session()
    sess.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (personal-edu-scraper; contact: you@example.com)"
            ),
            # Hint we prefer Serbian; some sites return region-specific markup.
            "Accept-Language": "sr-RS,sr;q=0.9,en;q=0.8",
        }
    )
    return sess


def detect_block(text: str) -> Optional[str]:
    """
    Find the first matching block code by testing alias regexes against text.
    Returns the block code or None if nothing matches.
    """
    if not text:
        return None
    low = text.lower()
    for code, aliases in BLOCK_ALIASES.items():
        for alias in aliases:
            # Use a simple substring/regex search; good enough for the first version.
            if re.search(alias, low):
                return code
    return None


@dataclass
class Listing:
    """
    Normalized listing shape emitted by scrapers.
    price_eur: integer euros; size and rooms are floats to preserve decimals.
    """

    source: str
    external_id: str
    city: str
    listing_type: str  # apartment, house, land
    block_code: str
    title: str
    price_eur: Optional[int]
    size_m2: Optional[float]
    rooms: Optional[float]
    floor: Optional[int]
    url: str
    thumbnail_url: Optional[str]
    is_agency: bool
    raw_text: str = ""
    raw_json: Optional[Dict] = None
    source_links: Optional[List[Dict]] = None
    is_duplicate: bool = False
    price_per_sqm: Optional[float] = None
    listing_date: Optional[str] = None  # ISO date string yyyy-mm-dd when available

    @property
    def dedupe_key(self) -> str:
        return build_dedupe_key(
            city=self.city,
            listing_type=self.listing_type,
            block_code=self.block_code,
            title=self.title,
        )

    def to_record(self, source_id: int) -> Dict:
        """
        Shape ready for DB insertion (matches listings table).
        """
        return {
            "source_id": source_id,
            "external_id": self.external_id,
            "city": self.city,
            "listing_type": self.listing_type,
            "block_code": self.block_code,
            "title": self.title,
            "price_eur": self.price_eur,
            "size_m2": self.size_m2,
            "rooms": self.rooms,
            "floor": self.floor,
            "url": self.url,
            "thumbnail_url": self.thumbnail_url,
            "is_agency": self.is_agency,
            "is_duplicate": self.is_duplicate,
            "price_per_sqm": self.price_per_sqm,
            "raw_text": self.raw_text,
            "raw_json": self.raw_json,
            "source_links": self.source_links,
            "dedupe_key": self.dedupe_key,
            "listing_date": self.listing_date,
        }


class RateLimiter:
    """
    Simple wall-clock rate limiter: enforces a minimum delay between calls.
    This keeps us polite without extra dependencies.
    """

    def __init__(self, min_delay_seconds: float = 1.0) -> None:
        self.min_delay_seconds = min_delay_seconds
        self._last = 0.0

    def wait(self) -> None:
        now = time.time()
        elapsed = now - self._last
        if elapsed < self.min_delay_seconds:
            time.sleep(self.min_delay_seconds - elapsed)
        self._last = time.time()


def chunk(iterable: Iterable, size: int):
    """
    Yield items in chunks of `size`. Handy for batch inserts later.
    """
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def to_number(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    digits = re.sub(r"[^\d,\.]", "", text)
    digits = digits.replace(".", "").replace(",", ".")
    try:
        return float(digits)
    except ValueError:
        return None


PRICE_RE = re.compile(r"([\d\.\s,]+)\s*€")


def parse_price_eur(text: str) -> Optional[int]:
    if not text:
        return None
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


ROOM_KEYWORDS = [
    (5.0, ["petosob", "petosoban", "petosobna", "5.0"]),
    (4.0, ["cetvorosob", "četvorosob", "4.0"]),
    (3.5, ["troiposob", "troiposoban", "3.5"]),
    (3.0, ["trosob", "trosoban", "3.0"]),
    (2.5, ["dvoiposob", "dvoiposoban", "2.5"]),
    (2.0, ["dvosob", "2.0"]),
    (1.5, ["jednoiposob", "1.5"]),
    (1.0, ["jednosob", "1.0"]),
    (0.5, ["garsonjera", "studio"]),
]


def detect_rooms(text: str) -> Optional[float]:
    low = text.lower()
    for val, keys in ROOM_KEYWORDS:
        for k in keys:
            if k in low:
                return val
    m = re.search(r"(\d+(?:\.\d)?)\s*sob", low)
    if m:
        try:
            rooms = float(m.group(1))
            if rooms > 8:
                return None
            return rooms
        except ValueError:
            return None
    return None


def detect_agency(text: str) -> bool:
    """
    Heuristic: check for 'agencija' token in the visible text.
    """
    return "agencija" in text.lower()


def _round_step(value: Optional[float], step: float) -> Optional[float]:
    if value is None:
        return None
    return round(value / step) * step


def _bucket_price(price_eur: Optional[int], bucket: int = 2000) -> Optional[int]:
    if price_eur is None:
        return None
    return int(round(price_eur / bucket) * bucket)


def _strip_ids(text: str) -> str:
    """
    Remove listing-id style tokens so title-based dedupe matches across sources.
    - Drops patterns like 'id#12345' or 'id 12345'
    - Drops standalone long digit tokens (5+ digits) often used as listing IDs
    """
    t = re.sub(r"id[#\s]*\d+", "", text, flags=re.IGNORECASE)
    t = re.sub(r"\b\d{5,}\b", "", t)
    return t


def _normalize_title(title: str) -> str:
    low = _strip_ids(title).lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", low).strip()
    return re.sub(r"\s+", " ", normalized)


def normalize_title_for_dedupe(title: str) -> str:
    """
    Public helper to normalize titles consistently for deduping across sources.
    """
    return _normalize_title(title)


def build_dedupe_key(
    *,
    city: str,
    listing_type: str,
    block_code: str,
    title: str,
) -> str:
    """
    Compose a stable dedupe key that tolerates diffs across sources.
    Use normalized title + block only (no price/size/rooms) to merge aggressively.
    Title normalization strips ID-like tokens to align cross-source copies.
    """
    title_norm = _normalize_title(title)
    raw = f"{city}|{listing_type}|{block_code}|{title_norm}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()

