-- Add duplicate flag and price per square meter.

ALTER TABLE listings
  ADD COLUMN is_duplicate BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN price_per_sqm NUMERIC(12,2);

CREATE INDEX IF NOT EXISTS listings_price_per_sqm_idx ON listings(price_per_sqm);

