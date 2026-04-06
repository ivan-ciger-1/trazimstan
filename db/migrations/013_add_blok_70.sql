-- Add Blok 70 (Novi Beograd) to the blocks table.
INSERT INTO blocks (code, name, aliases)
VALUES (
  'blok-70',
  'Blok 70',
  ARRAY['blok 70', 'block 70']
)
ON CONFLICT (code) DO NOTHING;
