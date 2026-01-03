-- Add cross-source deduplication key and thumbnail support.

ALTER TABLE listings
  ADD COLUMN dedupe_key TEXT,
  ADD COLUMN thumbnail_url TEXT,
  ADD COLUMN last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now();

-- Enforce uniqueness only when dedupe_key is present.
CREATE UNIQUE INDEX listings_dedupe_key_uidx
  ON listings(dedupe_key)
  WHERE dedupe_key IS NOT NULL;

CREATE INDEX listings_last_seen_idx ON listings(last_seen_at);

