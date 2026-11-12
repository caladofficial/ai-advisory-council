import React, { useEffect, useState } from "react";
import { ArrowRight, PlusCircle, RefreshCw, Scale, Trash2 } from "lucide-react";
import { api } from "../services/api";
import type { Investigation } from "../types";
import { Card, StatusBadge, VerdictBadge } from "../components/ui/Badges";

interface OverviewPageProps {
  onNewInvestigation: () => void;
  onOpenInvestigation: (id: string) => void;
}

export function OverviewPage({ onNewInvestigation, onOpenInvestigation }: OverviewPageProps) {
  const [items, setItems] = useState<Investigation[]>([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      setItems(await api.listInvestigations());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const completed = items.filter((i) => i.status === "COMPLETED").length;
  const active = items.filter((i) => !["COMPLETED", "FAILED", "CANCELLED", "CREATED"].includes(i.status)).length;

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    await api.deleteInvestigation(id);
    await load();
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-editorial text-3xl text-white">Advisory Council Dashboard</h1>
          <p className="text-sm text-slate-400 mt-1">
            Evidence-first investigations debated by 10 specialist AI advisors and adjudicated by an independent Chief Judge.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={load}
            className="px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 hover:bg-slate-800 text-xs font-medium text-slate-300 inline-flex items-center gap-1.5 cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
          <button
            type="button"
            onClick={onNewInvestigation}
            className="px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 text-sm font-semibold inline-flex items-center gap-2 shadow-lg shadow-amber-500/20 cursor-pointer"
          >
            <PlusCircle className="w-4 h-4" />
            <span>New Investigation</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        {[
          { label: "Total Investigations", value: items.length },
          { label: "Active Pipelines", value: active },
          { label: "Completed Verdicts", value: completed },
          { label: "API Spend (Zero-Paid)", value: "$0.00" },
        ].map((kpi) => (
          <Card key={kpi.label} className="p-4">
            <div className="text-xs text-slate-400">{kpi.label}</div>
            <div className="text-2xl font-bold font-mono text-white mt-1">{kpi.value}</div>
          </Card>
        ))}
      </div>

      <Card className="p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">Council Investigations</h2>
          <span className="text-xs text-slate-400">{items.length} records</span>
        </div>

        {loading ? (
          <p className="text-sm text-slate-400">Loading investigations...</p>
        ) : items.length === 0 ? (
          <div className="py-12 text-center space-y-3">
            <Scale className="w-10 h-10 text-slate-600 mx-auto" />
            <div className="text-sm text-slate-300 font-medium">No investigations submitted yet</div>
            <p className="text-xs text-slate-500 max-w-md mx-auto">
              Submit a business proposal, software architecture, scientific hypothesis, or policy decision to run the full 10 + 1 council workflow.
            </p>
            <button
              type="button"
              onClick={onNewInvestigation}
              className="px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-semibold cursor-pointer"
            >
              Launch First Investigation
            </button>
          </div>
        ) : (
          <div className="space-y-2.5">
            {items.map((inv) => (
              <div
                key={inv.investigation_id}
                onClick={() => onOpenInvestigation(inv.investigation_id)}
                className="p-4 rounded-xl bg-slate-950 border border-slate-800 hover:border-amber-500/40 transition-colors cursor-pointer flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="space-y-1.5 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-xs text-amber-400 font-semibold">{inv.investigation_id}</span>
                    <StatusBadge status={inv.status} />
                    <VerdictBadge verdict={inv.verdict} />
                    <span className="text-[11px] font-mono text-slate-500">
                      {inv.mode.replace(/_/g, " ")} · {inv.execution_profile === "prototype_3_plus_1" ? "3+1 Prototype" : "10+1 Council"}
                    </span>
                  </div>
                  <h3 className="text-sm font-medium text-white truncate">{inv.topic}</h3>
                  <div className="text-xs text-slate-400 flex flex-wrap gap-3">
                    <span>Domain: {inv.domain}</span>
                    <span>Geography: {inv.geography}</span>
                    {inv.readiness_score !== null && (
                      <span>Readiness: {inv.readiness_score}/100</span>
                    )}
                    {inv.feasibility_score !== null && (
                      <span className="text-amber-300 font-mono">Score: {inv.feasibility_score}/100</span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-3 shrink-0">
                  <div className="w-24">
                    <div className="text-right text-[11px] font-mono text-slate-400 mb-1">
                      {inv.progress_percent}%
                    </div>
                    <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
                      <div className="h-full bg-amber-400" style={{ width: `${inv.progress_percent}%` }} />
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => handleDelete(e, inv.investigation_id)}
                    className="p-2 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-slate-900 cursor-pointer"
                    title="Delete investigation"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                  <ArrowRight className="w-4 h-4 text-slate-500" />
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
