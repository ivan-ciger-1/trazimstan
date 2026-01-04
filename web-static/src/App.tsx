import { useEffect, useMemo, useState } from "react";
import "./index.css";
import listingsJson from "./data/listings.json";
import blocksJson from "./data/blocks.json";
import FiltersPanel from "./components/FiltersPanel";
import Header from "./components/Header";
import ListingsSection from "./components/ListingsSection";
import PageShell from "./components/PageShell";
import type { Block, Filters, Listing } from "./types";

const FALLBACK_BLOCKS: Block[] = [
  { code: "blok-67", name: "Blok 67 (Belville / A Blok)" },
  { code: "blok-38", name: "Blok 38" },
  { code: "blok-33", name: "Blok 33 (Genex)" },
];

const DEFAULT_FILTERS: Filters = {
  block: "",
  minPrice: "",
  maxPrice: "",
  minPricePerSqm: "",
  maxPricePerSqm: "",
  rooms: "",
  floor: "",
  isAgency: "",
  sort: "listing_date_desc",
};

const SORT_OPTIONS = [
  { value: "listing_date_desc", label: "Listing date (newest)" },
  { value: "listing_date_asc", label: "Listing date (oldest)" },
  { value: "price_desc", label: "Price (high → low)" },
  { value: "price_asc", label: "Price (low → high)" },
  { value: "price_per_sqm_desc", label: "€/m² (high → low)" },
  { value: "price_per_sqm_asc", label: "€/m² (low → high)" },
];

function deriveFiltersFromURL(): Filters {
  const params = new URLSearchParams(window.location.search);
  return {
    block: params.get("block") ?? "",
    minPrice: params.get("min_price") ?? "",
    maxPrice: params.get("max_price") ?? "",
    minPricePerSqm: params.get("min_price_per_sqm") ?? "",
    maxPricePerSqm: params.get("max_price_per_sqm") ?? "",
    rooms: params.get("rooms") ?? "",
    floor: params.get("floor") ?? "",
    isAgency: params.get("is_agency") ?? "",
    sort: params.get("sort") ?? "listing_date_desc",
  };
}

const ALL_LISTINGS: Listing[] = Array.isArray(listingsJson)
  ? listingsJson.map(normalizeListing)
  : [];
const ALL_BLOCKS: Block[] =
  Array.isArray(blocksJson) && blocksJson.length > 0
    ? blocksJson
    : FALLBACK_BLOCKS;
const LAST_UPDATED_RAW: string | null =
  ALL_LISTINGS.length > 0 ? ALL_LISTINGS[0].created_at ?? null : null;

function App() {
  const [filters, setFilters] = useState<Filters>(() =>
    deriveFiltersFromURL()
  );
  const [filtersOpen, setFiltersOpen] = useState(false);

  const availableRooms = useMemo(() => extractRooms(ALL_LISTINGS), []);
  const availableFloors = useMemo(() => extractFloors(ALL_LISTINGS), []);

  const roomOptions = useMemo(() => {
    const set = new Set(availableRooms);
    if (filters.rooms) set.add(filters.rooms);
    return Array.from(set).sort((a, b) => parseFloat(a) - parseFloat(b));
  }, [availableRooms, filters.rooms]);

  const floorOptions = useMemo(() => {
    const set = new Set(availableFloors);
    if (filters.floor) set.add(filters.floor);
    return Array.from(set).sort((a, b) => parseInt(a, 10) - parseInt(b, 10));
  }, [availableFloors, filters.floor]);

  const filtered = useMemo(() => {
    const out = ALL_LISTINGS.filter((l) => {
      if (filters.block && l.block !== filters.block) return false;
      if (filters.isAgency) {
        const expected = filters.isAgency === "true";
        if ((l.is_agency ?? false) !== expected) return false;
      }
      if (filters.rooms) {
        const v = parseFloat(filters.rooms);
        if (l.rooms !== v) return false;
      }
      if (filters.floor) {
        const v = parseInt(filters.floor, 10);
        if (l.floor !== v) return false;
      }
      if (filters.minPrice) {
        const v = parseInt(filters.minPrice, 10);
        if (l.price_eur !== null && l.price_eur < v) return false;
      }
      if (filters.maxPrice) {
        const v = parseInt(filters.maxPrice, 10);
        if (l.price_eur !== null && l.price_eur > v) return false;
      }
      if (filters.minPricePerSqm) {
        const v = parseFloat(filters.minPricePerSqm);
        if (l.price_per_sqm !== null && l.price_per_sqm < v) return false;
      }
      if (filters.maxPricePerSqm) {
        const v = parseFloat(filters.maxPricePerSqm);
        if (l.price_per_sqm !== null && l.price_per_sqm > v) return false;
      }
      return true;
    });

    const sorted = [...out].sort((a, b) => compareListings(a, b, filters.sort));
    return sorted;
  }, [filters]);

  const activeFilters = useMemo(
    () =>
      Object.entries(filters).filter(
        ([key, val]) => key !== "sort" && val !== ""
      ).length,
    [filters]
  );

  useEffect(() => {
    const params = new URLSearchParams();
    if (filters.block) params.set("block", filters.block);
    if (filters.minPrice) params.set("min_price", filters.minPrice);
    if (filters.maxPrice) params.set("max_price", filters.maxPrice);
    if (filters.minPricePerSqm)
      params.set("min_price_per_sqm", filters.minPricePerSqm);
    if (filters.maxPricePerSqm)
      params.set("max_price_per_sqm", filters.maxPricePerSqm);
    if (filters.rooms) params.set("rooms", filters.rooms);
    if (filters.floor) params.set("floor", filters.floor);
    if (filters.isAgency) params.set("is_agency", filters.isAgency);
    if (filters.sort && filters.sort !== "listing_date_desc")
      params.set("sort", filters.sort);
    const qs = params.toString();
    const newUrl = qs ? `?${qs}` : window.location.pathname;
    window.history.replaceState({}, "", newUrl);
  }, [filters]);

  const handleChange = (key: keyof Filters, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const resetFilters = () => {
    setFilters({ ...DEFAULT_FILTERS });
  };

  const lastUpdated = useMemo(() => {
    if (!LAST_UPDATED_RAW) return null;
    const candidate = LAST_UPDATED_RAW.replace(" ", "T");
    const dt = new Date(candidate);
    if (!Number.isNaN(dt.getTime())) {
      const formatter = new Intl.DateTimeFormat("en-GB", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      });
      return formatter.format(dt);
    }
    // Fallback: trim seconds if present (e.g., "2026-01-03 16:28:54.873386+01").
    const trimmed = LAST_UPDATED_RAW.replace(
      /(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}):\d{2}(\.\d+)?([+-]\d{2})?/,
      "$1$3"
    );
    return trimmed;
  }, []);

  return (
    <PageShell>
      <Header lastUpdated={lastUpdated} />
      <FiltersPanel
        filters={filters}
        filtersOpen={filtersOpen}
        activeFilters={activeFilters}
        blocks={ALL_BLOCKS}
        roomOptions={roomOptions}
        floorOptions={floorOptions}
        sortOptions={SORT_OPTIONS}
        onToggle={() => setFiltersOpen((v) => !v)}
        onChange={handleChange}
        onApply={() => setFilters((prev) => ({ ...prev }))}
        onReset={resetFilters}
      />
      <ListingsSection filtered={filtered} onReset={resetFilters} />
    </PageShell>
  );
}


function compareListings(a: Listing, b: Listing, sort: string): number {
  const getDate = (l: Listing) =>
    l.listing_date ? Date.parse(l.listing_date) || 0 : 0;
  const dateA = getDate(a);
  const dateB = getDate(b);
  const priceA = a.price_eur ?? Number.MAX_SAFE_INTEGER;
  const priceB = b.price_eur ?? Number.MAX_SAFE_INTEGER;
  const ppsqmA = a.price_per_sqm ?? Number.MAX_SAFE_INTEGER;
  const ppsqmB = b.price_per_sqm ?? Number.MAX_SAFE_INTEGER;

  switch (sort) {
    case "price_asc":
      return priceA - priceB || dateB - dateA;
    case "price_desc":
      return priceB - priceA || dateB - dateA;
    case "price_per_sqm_asc":
      return ppsqmA - ppsqmB || dateB - dateA;
    case "price_per_sqm_desc":
      return ppsqmB - ppsqmA || dateB - dateA;
    case "listing_date_asc":
      return dateA - dateB;
    case "listing_date_desc":
    default:
      return dateB - dateA;
  }
}

function extractRooms(data: Listing[]): string[] {
  const nums = data
    .map((l) => l.rooms)
    .filter((v): v is number => v !== null && v !== undefined);
  const set = new Set(nums.map((v) => v.toString()));
  return Array.from(set);
}

function extractFloors(data: Listing[]): string[] {
  const nums = data
    .map((l) => l.floor)
    .filter((v): v is number => v !== null && v !== undefined);
  const set = new Set(nums.map((v) => v.toString()));
  return Array.from(set);
}

function normalizeListing(l: any): Listing {
  return {
    id: Number(l.id ?? 0),
    block: l.block ?? l.block_code ?? "",
    title: l.title ?? "",
    price_eur:
      l.price_eur === null || l.price_eur === undefined
        ? null
        : Number(l.price_eur),
    size_m2:
      l.size_m2 === null || l.size_m2 === undefined ? null : Number(l.size_m2),
    rooms:
      l.rooms === null || l.rooms === undefined ? null : Number(l.rooms),
    floor:
      l.floor === null || l.floor === undefined ? null : Number(l.floor),
    url: l.url ?? "#",
    thumbnail_url: l.thumbnail_url ?? null,
    is_agency: !!l.is_agency,
    is_duplicate: !!l.is_duplicate,
    price_per_sqm:
      l.price_per_sqm === null || l.price_per_sqm === undefined
        ? null
        : Number(l.price_per_sqm),
    listing_date: l.listing_date ?? null,
    source_links: Array.isArray(l.source_links) ? l.source_links : [],
      created_at: l.created_at ? new Date(l.created_at).toLocaleString() : null,
  };
}

export default App;

