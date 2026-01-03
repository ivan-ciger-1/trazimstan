export type Listing = {
  id: number;
  block: string;
  title: string;
  price_eur?: number | null;
  size_m2?: number | null;
  rooms?: number | null;
  floor?: number | null;
  url: string;
  thumbnail_url?: string | null;
  is_agency?: boolean;
  is_duplicate?: boolean;
  price_per_sqm?: number | null;
  listing_date?: string | null;
  created_at?: string | null;
  source_links?: { source: string; url?: string; title?: string }[];
};

export type Block = { code: string; name: string };

export type Filters = {
  block: string;
  minPrice: string;
  maxPrice: string;
  minPricePerSqm: string;
  maxPricePerSqm: string;
  rooms: string;
  floor: string;
  isAgency: string;
  sort: string;
};

