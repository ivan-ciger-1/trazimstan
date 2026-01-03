-- Initial schema for apartment aggregation (prices in EUR).
-- Focus: blocks 67/38/33; extendable later.

CREATE TABLE blocks (
  code TEXT PRIMARY KEY,              -- stable identifier like 'blok-67'
  name TEXT NOT NULL UNIQUE,          -- human-friendly name
  aliases TEXT[] NOT NULL             -- lowercased alias list for detection
);

INSERT INTO blocks (code, name, aliases) VALUES
('blok-67', 'Blok 67 (Belville / A Blok)', ARRAY['blok 67','block 67','belville','a blok']),
('blok-38', 'Blok 38', ARRAY['blok 38','block 38']),
('blok-33', 'Blok 33 (Genex)', ARRAY['blok 33','block 33','genex', 'geneks']);

CREATE TABLE sources (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE           -- e.g., 'nekretnine.rs'
);

INSERT INTO sources (name) VALUES
('nekretnine.rs'),
('halooglasi'),
('kupujemprodajem'),
('4zida'),
('cityexpert'),
('oglasi.rs'),
('sasomange');

CREATE TABLE listings (
  id BIGSERIAL PRIMARY KEY,
  source_id INT NOT NULL REFERENCES sources(id),
  external_id TEXT NOT NULL,          -- id from the source site
  block_code TEXT NOT NULL REFERENCES blocks(code),
  title TEXT NOT NULL,
  price_eur BIGINT,                   -- store whole EUR; switch to cents if needed
  size_m2 NUMERIC(6,2),
  rooms NUMERIC(3,1),
  floor SMALLINT,
  url TEXT NOT NULL,
  raw_text TEXT,
  raw_json JSONB,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX listings_source_ext_uidx ON listings(source_id, external_id);
CREATE INDEX listings_block_idx ON listings(block_code);
CREATE INDEX listings_price_idx ON listings(price_eur);
CREATE INDEX listings_size_idx ON listings(size_m2);

-- Optional observability: track scrape runs per source.
CREATE TABLE scrape_runs (
  id BIGSERIAL PRIMARY KEY,
  source_id INT NOT NULL REFERENCES sources(id),
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ,
  status TEXT NOT NULL CHECK (status IN ('running','success','failed')),
  note TEXT
);

