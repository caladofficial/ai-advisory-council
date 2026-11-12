import React, { useEffect, useState } from "react";
import { api } from "../services/api";
import type { AuditEventItem, ModelUsageItem } from "../types";
import { Card } from "../components/ui/Badges";

export function SystemAuditPage() {
  const [events, setEvents] = useState<AuditEventItem[]>([]);
  const [usage, setUsage] = useState<ModelUsageItem[]>([]);

  useEffect(() => {
    Promise.all([api.getGlobalAudit(), api.getGlobalUsage()]).then(([e, u]) => {
      setEvents(e);
      setUsage(u);
    });
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-editorial text-3xl text-white">System Audit &amp; Usage Ledger</h1>
        <p className="text-sm text-slate-400 mt-1">
          Append-only record of investigation transitions, key configurations, and zero-cost LLM calls.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card className="p-5 space-y-3">
          <h2 className="text-sm font-semibold text-white">Recent Audit Events</h2>
          <div className="space-y-2 max-h-[600px] overflow-y-auto">
            {events.map((ev) => (
              <div key={ev.event_id} className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs space-y-1">
                <div className="flex justify-between font-mono text-[11px] text-slate-400">
                  <span>{ev.investigation_id || "SYSTEM"} · {ev.event_type}</span>
                  <span>{new Date(ev.created_at).toLocaleString()}</span>
                </div>
                <p className="text-slate-200">{ev.summary}</p>
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-5 space-y-3">
          <h2 className="text-sm font-semibold text-white">Recent Model Executions</h2>
          <div className="space-y-2 max-h-[600px] overflow-y-auto">
            {usage.map((u) => (
              <div key={u.usage_id} className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs flex justify-between items-center gap-2">
                <div>
                  <div className="font-mono text-white">
                    {u.investigation_id || "PROBE"} · {u.agent_id}
                  </div>
                  <div className="text-[11px] text-slate-400">
                    {u.provider}:{u.model_id} · {u.total_tokens} tok · {u.latency_ms}ms · {u.status}
                  </div>
                </div>
                <span className="font-mono text-emerald-300">$0.00</span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
