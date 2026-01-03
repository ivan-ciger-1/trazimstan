import type { ReactNode } from "react";

function PageShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen text-slate-100">
      <div className="mx-auto max-w-6xl px-3 sm:px-4 md:px-6 py-6 sm:py-8 space-y-6">
        {children}
      </div>
    </div>
  );
}

export default PageShell;

