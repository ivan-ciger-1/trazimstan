-- Seed a generic block entry for Pančevo to satisfy FK on listings.block_code.
INSERT INTO blocks (code, name, aliases)
VALUES ('pancevo', 'Pančevo', ARRAY['pancevo', 'pančevo'])
ON CONFLICT (code) DO NOTHING;
