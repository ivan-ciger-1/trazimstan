-- Add listing_date (date the listing was posted, when available).

ALTER TABLE listings
  ADD COLUMN listing_date DATE;

CREATE INDEX IF NOT EXISTS listings_listing_date_idx ON listings(listing_date);

