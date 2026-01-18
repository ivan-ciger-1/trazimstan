-- Add city and listing_type to classify listings by geography and property type.
ALTER TABLE listings
    ADD COLUMN IF NOT EXISTS city TEXT NOT NULL DEFAULT 'belgrade',
    ADD COLUMN IF NOT EXISTS listing_type TEXT NOT NULL DEFAULT 'apartment';

-- Helpful index for city/type filtering and ordering by date.
CREATE INDEX IF NOT EXISTS idx_listings_city_type_date
    ON listings (city, listing_type, listing_date DESC);
