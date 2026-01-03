import type { Listing } from "../types";
import Badge from "./Badge";

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
      className="group relative overflow-hidden rounded-2xl border border-white/5 bg-white/5 backdrop-blur transition hover:border-purple-400/50 hover:bg-white/10"
    >
      <div className="flex flex-col md:grid md:grid-cols-[180px,1fr] md:gap-0">
        <div className="relative w-full aspect-[4/3] md:aspect-auto md:h-full md:min-h-[180px] bg-slate-900">
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
            <Badge tone="amber">{item.block}</Badge>
            {item.is_agency ? <Badge tone="amber">Agency</Badge> : null}
          </div>
        </div>
        <div className="p-4 space-y-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div className="space-y-1">
              <p className="text-xs text-slate-400">ID #{item.id}</p>
              <h3 className="text-base sm:text-lg font-semibold leading-snug text-white">
                {item.title}
              </h3>
            </div>
            <div className="flex flex-wrap sm:flex-col sm:items-end gap-x-3 gap-y-1 text-right">
              <div className="text-lg sm:text-xl font-bold text-white flex items-baseline justify-end gap-1 whitespace-nowrap">
                <span>{price}</span>
              </div>
              <div className="text-xs text-slate-400">{pricePerSqm}</div>
            </div>
          </div>

          <div className="flex flex-wrap gap-2 text-xs text-slate-300">
            {item.size_m2 ? (
              <Badge tone="indigo" variant="ghost">
                {item.size_m2} m²
              </Badge>
            ) : null}
            {item.rooms ? (
              <Badge tone="purple" variant="ghost">
                {item.rooms} rooms
              </Badge>
            ) : null}
            {item.floor !== null && item.floor !== undefined ? (
              <Badge tone="blue" variant="ghost">
                Floor {item.floor}
              </Badge>
            ) : null}
            {item.listing_date ? (
              <Badge tone="emerald" variant="ghost">
                Posted {item.listing_date}
              </Badge>
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
                    className="rounded-full bg-slate-800/80 px-2 py-1 underline decoration-slate-500/60 hover:decoration-purple-400"
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

function formatMoney(val: number | null | undefined) {
  if (val === null || val === undefined) return "—";
  return `${val.toLocaleString("sr-RS")} €`;
}

export default ListingCard;

