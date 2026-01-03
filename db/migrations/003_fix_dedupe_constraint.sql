-- Replace partial unique index with a proper unique constraint on dedupe_key
-- so ON CONFLICT (dedupe_key) works.

-- Drop old partial index if it exists.
DROP INDEX IF EXISTS listings_dedupe_key_uidx;

-- Add unique constraint (allows multiple NULLs by default).
ALTER TABLE listings
  ADD CONSTRAINT listings_dedupe_key_uniq UNIQUE (dedupe_key);

-- Recreate supporting index on last_seen_at if missing (harmless if exists).
CREATE INDEX IF NOT EXISTS listings_last_seen_idx ON listings(last_seen_at);

