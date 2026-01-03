type HeaderProps = {
  lastUpdated: string | null;
};

function Header({ lastUpdated }: HeaderProps) {
  const display = lastUpdated ? lastUpdated : "N/A";
  return (
    <header className="flex flex-col gap-2">
      <p className="text-sm text-slate-400">Belgrade · Novi Beograd</p>
      <h1 className="text-3xl font-semibold tracking-tight">
        Apartment Listings
      </h1>
      <p className="text-slate-400">
        Last updated at:{" "}
        <span className="font-semibold text-slate-200">{display}</span>
      </p>
    </header>
  );
}

export default Header;

