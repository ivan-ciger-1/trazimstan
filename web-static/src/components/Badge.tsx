import type { ReactNode } from "react";

type Tone = "blue" | "purple" | "indigo" | "emerald" | "amber" | "slate";
type Variant = "solid" | "ghost";

function Badge({
  children,
  tone = "purple",
  variant = "solid",
}: {
  children: ReactNode;
  tone?: Tone;
  variant?: Variant;
}) {
  const tonesSolid: Record<Tone, string> = {
    blue: "bg-indigo-500 text-white border border-indigo-400 shadow-sm shadow-indigo-500/30",
    purple:
      "bg-purple-600 text-white border border-purple-400 shadow-sm shadow-purple-500/30",
    indigo:
      "bg-indigo-600 text-white border border-indigo-400 shadow-sm shadow-indigo-500/30",
    emerald:
      "bg-emerald-500 text-white border border-emerald-400 shadow-sm shadow-emerald-500/25",
    amber:
      "bg-amber-400 text-slate-900 border border-amber-300 shadow-sm shadow-amber-400/30",
    slate:
      "bg-slate-600 text-white border border-slate-400 shadow-sm shadow-slate-600/30",
  };
  const tonesGhost: Record<Tone, string> = {
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

export default Badge;

