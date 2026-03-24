-- Add Blok 64 and Blok 65 to the blocks table.
INSERT INTO blocks (code, name, aliases)
VALUES
  ('blok-64', 'Blok 64', ARRAY['blok 64', 'block 64']),
  ('blok-65', 'Blok 65', ARRAY['blok 65', 'block 65'])
ON CONFLICT (code) DO NOTHING;
