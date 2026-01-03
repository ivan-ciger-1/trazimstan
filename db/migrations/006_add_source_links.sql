-- Store all source URLs for merged duplicates.

ALTER TABLE listings
  ADD COLUMN source_links JSONB;

