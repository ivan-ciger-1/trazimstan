-- Land listings can exceed 10,000 m2; widen size_m2 to avoid overflow.
ALTER TABLE listings
    ALTER COLUMN size_m2 TYPE NUMERIC(12,2)
    USING size_m2;
