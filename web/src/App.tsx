import { useEffect, useMemo, useState, type ReactNode } from "react";
import "./index.css";

type Listing = {
  id: number;
  block: string;
  title: string;
  price_eur: number | null;
  size_m2: number | null;
  rooms: number | null;
  floor: number | null;
  url: string;
  thumbnail_url?: string | null;
  is_agency?: boolean;
  is_duplicate?: boolean;
  price_per_sqm?: number | null;
  listing_date?: string | null;
  source_links?: { source: string; url?: string; title?: string }[];
};

type Block = { code: string; name: string };

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8080";
const DEFAULT_LIMIT = 50;

const SORT_OPTIONS = [
  { value: "listing_date_desc", label: "Listing date (newest)" },
  { value: "listing_date_asc", label: "Listing date (oldest)" },
  { value: "price_desc", label: "Price (high → low)" },
  { value: "price_asc", label: "Price (low → high)" },
  { value: "price_per_sqm_desc", label: "€/m² (high → low)" },
  { value: "price_per_sqm_asc", label: "€/m² (low → high)" },
];

const FALLBACK_BLOCKS: Block[] = [
  { code: "blok-67", name: "Blok 67 (Belville / A Blok)" },
  { code: "blok-38", name: "Blok 38" },
  { code: "blok-33", name: "Blok 33 (Genex)" },
];

type Filters = {
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

const initialFilters: Filters = {
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

function App() {
  const [filters, setFilters] = useState<Filters>(initialFilters);
  const [filtersOpen, setFiltersOpen] = useState(true);
  const [listings, setListings] = useState<Listing[]>([]);
  const [availableRooms, setAvailableRooms] = useState<string[]>([]);
  const [availableFloors, setAvailableFloors] = useState<string[]>([]);
  const [blocks, setBlocks] = useState<Block[]>(FALLBACK_BLOCKS);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const activeFilters = useMemo(
    () =>
      Object.entries(filters).filter(
        ([key, val]) => key !== "sort" && val !== ""
      ).length,
    [filters]
  );

  useEffect(() => {
    loadBlocks();
    fetchListings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadBlocks = async () => {
    try {
      const res = await fetch(`${API_BASE}/blocks`);
      if (!res.ok) return;
      const data: Block[] = await res.json();
      if (Array.isArray(data) && data.length) {
        setBlocks(data);
      }
    } catch (e) {
      // keep fallback blocks
      console.warn("blocks fetch failed", e);
    }
  };

  const fetchListings = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set("limit", String(DEFAULT_LIMIT));
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
      if (filters.sort) params.set("sort", filters.sort);

      const res = await fetch(`${API_BASE}/listings?${params.toString()}`);
      if (!res.ok) {
        throw new Error(`API error ${res.status}`);
      }
      const data = await res.json();
      const parsed: Listing[] = Array.isArray(data) ? data : [];
      setListings(parsed);
      setAvailableRooms(extractRooms(parsed));
      setAvailableFloors(extractFloors(parsed));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load listings");
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (key: keyof Filters, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const resetFilters = () => {
    setFilters(initialFilters);
    setTimeout(fetchListings, 0);
  };

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

  return (
    <div className="min-h-screen text-slate-100">
      <div className="mx-auto max-w-6xl px-4 py-6 space-y-6">
        <header className="flex flex-col gap-2">
          <p className="text-sm text-slate-400">Belgrade · Novi Beograd</p>
          <h1 className="text-3xl font-semibold tracking-tight">
            Apartment Listings
          </h1>
          <p className="text-slate-400">
            Browse fresh listings with quick filters. Data powered by the Go API
            on <span className="font-mono">{API_BASE}</span>.
          </p>
        </header>

        <section className="rounded-2xl border border-white/5 bg-white/5 backdrop-blur p-4 shadow-lg space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="text-lg font-semibold">Filters</h2>
              {activeFilters > 0 && (
                <span className="rounded-full bg-blue-500/15 px-3 py-1 text-sm text-blue-100">
                  {activeFilters} applied
                </span>
              )}
            </div>
            <button
              type="button"
              className="btn-ghost px-3 py-2 text-xs sm:text-sm"
              onClick={() => setFiltersOpen((v) => !v)}
            >
              {filtersOpen ? "Hide filters" : "Show filters"}
            </button>
          </div>
          {filtersOpen && (
            <form
              className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3"
              onSubmit={(e) => {
                e.preventDefault();
                fetchListings();
              }}
            >
              <FilterField label="Block">
                <select
                  className="input"
                  value={filters.block}
                  onChange={(e) => handleChange("block", e.target.value)}
                >
                  <option value="">Any</option>
                  {blocks.map((b) => (
                    <option key={b.code} value={b.code}>
                      {b.name}
                    </option>
                  ))}
                </select>
              </FilterField>

              <FilterField label="Price min (€)">
                <input
                  className="input"
                  type="number"
                  inputMode="numeric"
                  value={filters.minPrice}
                  onChange={(e) => handleChange("minPrice", e.target.value)}
                />
              </FilterField>

              <FilterField label="Price max (€)">
                <input
                  className="input"
                  type="number"
                  inputMode="numeric"
                  value={filters.maxPrice}
                  onChange={(e) => handleChange("maxPrice", e.target.value)}
                />
              </FilterField>

              <FilterField label="€/m² min">
                <input
                  className="input"
                  type="number"
                  inputMode="numeric"
                  value={filters.minPricePerSqm}
                  onChange={(e) =>
                    handleChange("minPricePerSqm", e.target.value)
                  }
                />
              </FilterField>

              <FilterField label="€/m² max">
                <input
                  className="input"
                  type="number"
                  inputMode="numeric"
                  value={filters.maxPricePerSqm}
                  onChange={(e) =>
                    handleChange("maxPricePerSqm", e.target.value)
                  }
                />
              </FilterField>

              <FilterField label="Rooms">
                <select
                  className="input"
                  value={filters.rooms}
                  onChange={(e) => handleChange("rooms", e.target.value)}
                >
                  <option value="">Any</option>
                  {roomOptions.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
              </FilterField>

              <FilterField label="Floor">
                <select
                  className="input"
                  value={filters.floor}
                  onChange={(e) => handleChange("floor", e.target.value)}
                >
                  <option value="">Any</option>
                  {floorOptions.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt === "-1" ? "Basement (-1)" : opt === "0" ? "Ground (0)" : opt}
                    </option>
                  ))}
                </select>
              </FilterField>

              <FilterField label="Agency?">
                <select
                  className="input"
                  value={filters.isAgency}
                  onChange={(e) => handleChange("isAgency", e.target.value)}
                >
                  <option value="">Any</option>
                  <option value="true">Only agency</option>
                  <option value="false">Only owner</option>
                </select>
              </FilterField>

              <FilterField label="Sort">
                <select
                  className="input"
                  value={filters.sort}
                  onChange={(e) => handleChange("sort", e.target.value)}
                >
                  {SORT_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </FilterField>

              <div className="sm:col-span-2 lg:col-span-3 flex flex-wrap gap-3 pt-1">
                <button
                  type="submit"
                  className="btn-primary"
                  disabled={loading}
                >
                  {loading ? "Loading…" : "Apply filters"}
                </button>
                <button
                  type="button"
                  className="btn-ghost"
                  onClick={resetFilters}
                  disabled={loading}
                >
                  Reset
                </button>
              </div>
            </form>
          )}
        </section>

        {error && (
          <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-100">
            {error}
          </div>
        )}

        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Listings</h2>
            <span className="text-sm text-slate-400">
              {loading
                ? "Loading…"
                : `${listings.length} result${listings.length === 1 ? "" : "s"}`}
            </span>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Array.from({ length: 4 }).map((_, idx) => (
                <div
                  key={idx}
                  className="animate-pulse rounded-2xl bg-white/5 h-48 border border-white/5"
                />
              ))}
            </div>
          ) : listings.length === 0 ? (
            <div className="rounded-2xl border border-white/5 bg-white/5 p-6 text-slate-200 shadow-lg">
              <div className="flex items-start gap-3">
                <div className="mt-1 h-8 w-8 rounded-full bg-purple-500/20 text-purple-100 flex items-center justify-center font-semibold">
                  !
                </div>
                <div className="space-y-1">
                  <h3 className="text-lg font-semibold">No listings found</h3>
                  <p className="text-sm text-slate-400">
                    Try broadening filters or resetting to see all recent listings.
                  </p>
                  <div className="flex gap-2 pt-2">
                    <button
                      type="button"
                      className="btn-primary"
                      onClick={resetFilters}
                    >
                      Reset filters
                    </button>
                    <button
                      type="button"
                      className="btn-ghost"
                      onClick={fetchListings}
                    >
                      Refresh
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {listings.map((item) => (
                <ListingCard key={item.id} item={item} />
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function ListingCard({ item }: { item: Listing }) {
  const price = formatMoney(item.price_eur);
  const pricePerSqm = item.price_per_sqm
    ? `${Math.round(item.price_per_sqm).toLocaleString("sr-RS")} €/m²`
    : "—";

  return (
    <a
      href={item.url}
      target="_blank"
      rel="noreferrer"
      className="group relative overflow-hidden rounded-2xl border border-white/5 bg-white/5 backdrop-blur transition hover:border-blue-400/50 hover:bg-white/10"
    >
      <div className="grid grid-cols-[120px,1fr] md:grid-cols-[160px,1fr]">
        <div className="relative h-full min-h-[140px] bg-slate-900">
          {item.thumbnail_url ? (
            <img
              src={item.thumbnail_url}
              alt={item.title}
              className="h-full w-full object-cover"
              loading="lazy"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-slate-500 text-sm">
              No photo
            </div>
          )}
          <div className="absolute left-2 top-2 flex gap-2">
            <Badge >{item.block}</Badge>
            {item.is_agency ? <Badge tone="amber">Agency</Badge> : null}
          </div>
        </div>
        <div className="p-4 space-y-2">
          <div className="flex items-start justify-between gap-3">
            <h3 className="text-base font-semibold leading-snug text-white">
              {item.title}
            </h3>
            <div className="text-right">
              <div className="text-lg font-bold text-white flex items-baseline justify-end gap-1 whitespace-nowrap">
                <span>{price}</span>
              </div>
              <div className="text-xs text-slate-400">{pricePerSqm}</div>
            </div>
          </div>

          <div className="flex flex-wrap gap-2 text-xs text-slate-300">
            {item.size_m2 ? <Badge tone="indigo" variant="ghost">{item.size_m2} m²</Badge> : null}
            {item.rooms ? <Badge tone="purple" variant="ghost">{item.rooms} rooms</Badge> : null}
            {item.floor !== null && item.floor !== undefined ? (
              <Badge tone="blue" variant="ghost">Floor {item.floor}</Badge>
            ) : null}
            {item.listing_date ? (
              <Badge tone="emerald" variant="ghost">Posted {item.listing_date}</Badge>
            ) : null}
          </div>

          {item.source_links && item.source_links.length > 0 && (
            <div className="pt-2 text-xs text-slate-400 flex flex-wrap gap-2">
              {item.source_links.map((s, idx) => {
                const label = s.source || "link";
                return s.url ? (
                  <a
                    key={idx}
                    href={s.url}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-full bg-slate-800/80 px-2 py-1 underline decoration-slate-500/60 hover:decoration-blue-400"
                    title={s.title || s.url}
                  >
                    {label}
                  </a>
                ) : (
                  <span
                    key={idx}
                    className="rounded-full bg-slate-800/80 px-2 py-1"
                  >
                    {label}
                  </span>
                );
              })}
            </div>
          )}
        </div>
      </div>
      <div className="absolute inset-0 pointer-events-none opacity-0 group-hover:opacity-100 transition duration-150 bg-gradient-to-r from-purple-500/12 to-transparent" />
    </a>
  );
}

function Badge({
  children,
  tone = "purple",
  variant = "solid",
}: {
  children: ReactNode;
  tone?: "blue" | "purple" | "indigo" | "emerald" | "amber" | "slate";
  variant?: "solid" | "ghost";
}) {
  const tonesSolid: Record<typeof tone, string> = {
    blue: "bg-indigo-500 text-white border border-indigo-400 shadow-sm shadow-indigo-500/30",
    purple: "bg-purple-600 text-white border border-purple-400 shadow-sm shadow-purple-500/30",
    indigo: "bg-indigo-600 text-white border border-indigo-400 shadow-sm shadow-indigo-500/30",
    emerald: "bg-emerald-500 text-white border border-emerald-400 shadow-sm shadow-emerald-500/25",
    amber: "bg-amber-400 text-slate-900 border border-amber-300 shadow-sm shadow-amber-400/30",
    slate: "bg-slate-600 text-white border border-slate-400 shadow-sm shadow-slate-600/30",
  };
  const tonesGhost: Record<typeof tone, string> = {
    blue: "bg-indigo-500/18 text-indigo-100 border-indigo-400/40",
    purple: "bg-purple-500/18 text-purple-50 border-purple-400/45",
    indigo: "bg-indigo-500/18 text-indigo-100 border-indigo-400/40",
    emerald: "bg-emerald-500/18 text-emerald-100 border-emerald-400/35",
    amber: "bg-amber-500/18 text-amber-100 border-amber-400/35",
    slate: "bg-slate-500/22 text-slate-100 border-slate-400/35",
  };
  const palette = variant === "ghost" ? tonesGhost : tonesSolid;
  return (
    <span
      className={`rounded-full border px-2 py-1 text-[11px] font-medium ${palette[tone]}`}
    >
      {children}
    </span>
  );
}

function FilterField({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1 text-sm text-slate-200">
      <span className="text-xs uppercase tracking-wide text-slate-400">
        {label}
      </span>
      {children}
    </label>
  );
}

function formatMoney(val: number | null | undefined) {
  if (val === null || val === undefined) return "—";
  return `${val.toLocaleString("sr-RS")} €`;
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

export default App;
