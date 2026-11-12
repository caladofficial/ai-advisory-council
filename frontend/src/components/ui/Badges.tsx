import React from "react";

const VERDICT_STYLES: Record<string, string> = {
  GO: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
  CONDITIONAL_GO: "bg-teal-500/15 text-teal-300 border-teal-500/40",
  PILOT_FIRST: "bg-amber-500/15 text-amber-300 border-amber-500/40",
  PIVOT: "bg-orange-500/15 text-orange-300 border-orange-500/40",
  NO_GO: "bg-rose-500/15 text-rose-300 border-rose-500/40",
  INSUFFICIENT_EVIDENCE: "bg-slate-600/20 text-slate-300 border-slate-500/40",
};

const STANCE_STYLES: Record<string, string> = {
  SUPPORT: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  CONDITIONAL: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  OPPOSE: "bg-rose-500/15 text-rose-300 border-rose-500/30",
  INSUFFICIENT_EVIDENCE: "bg-slate-600/20 text-slate-300 border-slate-500/30",
};

const VERIF_STYLES: Record<string, string> = {
  VERIFIED: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  CORROBORATED: "bg-cyan-500/15 text-cyan-300 border-cyan-500/30",
  PARTIALLY_SUPPORTED: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  CONTRADICTED: "bg-rose-500/15 text-rose-300 border-rose-500/30",
  UNVERIFIED: "bg-slate-700/40 text-slate-300 border-slate-600/40",
  OUTDATED: "bg-orange-500/15 text-orange-300 border-orange-500/30",
};

export function VerdictBadge({ verdict }: { verdict: string | null | undefined }) {
  if (!verdict) return <span className="text-xs text-slate-500">Pending</span>;
  const cls = VERDICT_STYLES[verdict] || "bg-slate-700 text-slate-200 border-slate-600";
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${cls}`}>
      {verdict.replace(/_/g, " ")}
    </span>
  );
}

export function StanceBadge({ stance }: { stance: string }) {
  const cls = STANCE_STYLES[stance] || "bg-slate-700 text-slate-200 border-slate-600";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold border ${cls}`}>
      {stance.replace(/_/g, " ")}
    </span>
  );
}

export function VerificationBadge({ status }: { status: string }) {
  const cls = VERIF_STYLES[status] || "bg-slate-700 text-slate-300 border-slate-600";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium border ${cls}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  let cls = "bg-slate-800 text-slate-300 border-slate-700";
  if (status === "COMPLETED" || status === "completed" || status === "healthy") {
    cls = "bg-emerald-500/15 text-emerald-300 border-emerald-500/30";
  } else if (["FAILED", "CANCELLED", "unavailable"].includes(status)) {
    cls = "bg-rose-500/15 text-rose-300 border-rose-500/30";
  } else if (["PAUSED", "NEEDS_USER_INPUT", "INSUFFICIENT_EVIDENCE", "READY_WITH_WARNINGS"].includes(status)) {
    cls = "bg-amber-500/15 text-amber-300 border-amber-500/30";
  } else if (status !== "CREATED" && status !== "idle" && status !== "pending") {
    cls = "bg-sky-500/15 text-sky-300 border-sky-500/30";
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono font-medium border ${cls}`}>
      {status}
    </span>
  );
}

export function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`bg-slate-900/80 border border-slate-800 rounded-xl shadow-sm ${className}`}>
      {children}
    </div>
  );
}

export function EvidenceChip({
  id,
  onClick,
}: {
  id: string;
  onClick: (evdId: string) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onClick(id)}
      className="inline-flex items-center px-1.5 py-0.5 rounded bg-sky-500/10 hover:bg-sky-500/25 text-sky-300 border border-sky-500/30 font-mono text-[11px] transition-colors cursor-pointer"
    >
      {id}
    </button>
  );
}
