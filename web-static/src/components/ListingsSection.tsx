import type { Listing } from "../types";
import EmptyState from "./EmptyState";
import ListingCard from "./ListingCard";

type ListingsSectionProps = {
  filtered: Listing[];
  onReset: () => void;
};

function ListingsSection({ filtered, onReset }: ListingsSectionProps) {
  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">Listings</h2>
        <span className="text-sm text-slate-400">
          {`${filtered.length} result${filtered.length === 1 ? "" : "s"}`}
        </span>
      </div>

      {filtered.length === 0 ? (
        <EmptyState onReset={onReset} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-4">
          {filtered.map((item) => (
            <ListingCard key={item.id} item={item} />
          ))}
        </div>
      )}
    </section>
  );
}

export default ListingsSection;

