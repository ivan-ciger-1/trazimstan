type HeaderProps = {
  lastUpdated: string | null;
  city: string;
};

function Header({ lastUpdated, city }: HeaderProps) {
  const display = lastUpdated ? lastUpdated : "N/A";
  const cityLabel = city.charAt(0).toUpperCase() + city.slice(1);
  const subtitle = city === "belgrade" ? "Belgrade · Novi Beograd" : cityLabel;
  return (
    <header className="flex flex-col gap-2">
      <h1 className="text-xl font-semibold tracking-tight">
        {subtitle} Listings
      </h1>
      <p className="text-slate-400">
        Last updated at:{" "}
        <span className="font-semibold text-slate-200">{display}</span>
      </p>
    </header>
  );
}

export default Header;

