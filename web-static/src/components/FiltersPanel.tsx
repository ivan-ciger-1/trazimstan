import type { Block, Filters } from "../types";
import FilterField from "./FilterField";

type FiltersPanelProps = {
  filters: Filters;
  filtersOpen: boolean;
  activeFilters: number;
  roomOptions: string[];
  floorOptions: string[];
  blocks: Block[];
  sortOptions: { value: string; label: string }[];
  onChange: (key: keyof Filters, value: string) => void;
  onToggle: () => void;
  onApply: () => void;
  onReset: () => void;
};

function FiltersPanel({
  filters,
  filtersOpen,
  activeFilters,
  roomOptions,
  floorOptions,
  blocks,
  sortOptions,
  onChange,
  onToggle,
  onApply,
  onReset,
}: FiltersPanelProps) {
  return (
    <section className="rounded-2xl border border-white/5 bg-white/5 backdrop-blur p-4 shadow-lg space-y-4">
      <div className="flex flex-wrap items-start sm:items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-lg font-semibold">Filters</h2>
          {activeFilters > 0 && (
            <span className="rounded-full bg-purple-500/20 px-3 py-1 text-sm text-purple-50">
              {activeFilters} applied
            </span>
          )}
        </div>
        <button
          type="button"
          className="btn-ghost px-3 py-2 text-xs sm:text-sm"
          onClick={onToggle}
        >
          {filtersOpen ? "Hide filters" : "Show filters"}
        </button>
      </div>
      {filtersOpen && (
        <form
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3"
          onSubmit={(e) => e.preventDefault()}
        >
          <FilterField label="Block">
            <select
              className="input"
              value={filters.block}
              onChange={(e) => onChange("block", e.target.value)}
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
              onChange={(e) => onChange("minPrice", e.target.value)}
            />
          </FilterField>

          <FilterField label="Price max (€)">
            <input
              className="input"
              type="number"
              inputMode="numeric"
              value={filters.maxPrice}
              onChange={(e) => onChange("maxPrice", e.target.value)}
            />
          </FilterField>

          <FilterField label="€/m² min">
            <input
              className="input"
              type="number"
              inputMode="numeric"
              value={filters.minPricePerSqm}
              onChange={(e) => onChange("minPricePerSqm", e.target.value)}
            />
          </FilterField>

          <FilterField label="€/m² max">
            <input
              className="input"
              type="number"
              inputMode="numeric"
              value={filters.maxPricePerSqm}
              onChange={(e) => onChange("maxPricePerSqm", e.target.value)}
            />
          </FilterField>

          <FilterField label="Rooms">
            <select
              className="input"
              value={filters.rooms}
              onChange={(e) => onChange("rooms", e.target.value)}
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
              onChange={(e) => onChange("floor", e.target.value)}
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
              onChange={(e) => onChange("isAgency", e.target.value)}
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
              onChange={(e) => onChange("sort", e.target.value)}
            >
              {sortOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </FilterField>

          <div className="sm:col-span-2 lg:col-span-3 flex flex-wrap gap-3 pt-1">
            <button type="button" className="btn-primary" onClick={onApply}>
              Apply filters
            </button>
            <button type="button" className="btn-ghost" onClick={onReset}>
              Reset
            </button>
          </div>
        </form>
      )}
    </section>
  );
}

export default FiltersPanel;

