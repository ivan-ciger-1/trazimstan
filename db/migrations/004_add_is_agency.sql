-- Add flag to mark whether a listing is posted by an agency.

ALTER TABLE listings
  ADD COLUMN is_agency BOOLEAN NOT NULL DEFAULT false;

