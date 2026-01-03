-- Drop the unique index on dedupe_key and replace with a plain index.
-- We rely on app-level dedupe/upsert keyed by source_id+external_id.

DROP INDEX IF EXISTS listings_dedupe_key_uniq;
ALTER TABLE listings DROP CONSTRAINT IF EXISTS listings_dedupe_key_uniq;

CREATE INDEX IF NOT EXISTS listings_dedupe_key_idx ON listings(dedupe_key);

