import React from "react";
import { AlertOctagon, CheckCircle2, Gavel, ShieldAlert } from "lucide-react";
import type { JudgeEvaluation } from "../../types";
import { Card, VerdictBadge } from "../ui/Badges";

export function ScorecardPanel({ judge }: { judge: JudgeEvaluation }) {
  return (
    <div className="space-y-6">
      <Card className="p-6 border-amber-500/30 bg-gradient-to-br from-slate-900 to-slate-950">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-2.5 flex-wrap">
              <Gavel className="w-5 h-5 text-amber-400" />
              <span className="text-xs font-mono uppercase tracking-wider text-amber-400">
                Eleventh Authority · Independent Chief Judge
              </span>
              <VerdictBadge verdict={judge.verdict} />
              {judge.disagreed_with_majority && (
                <span className="px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 text-xs font-medium">
                  Diverged from Advisor Majority
                </span>
              )}
            </div>
            <h2 className="font-editorial text-2xl text-white">Feasibility Adjudication</h2>
            <p className="text-sm text-slate-300 leading-relaxed max-w-3xl">{judge.executive_summary}</p>
            <p className="text-xs text-slate-400">{judge.decision_rationale}</p>
          </div>

          <div className="shrink-0 bg-slate-950 border border-slate-800 rounded-xl p-5 text-center min-w-44">
            <div className="text-xs uppercase tracking-wider text-slate-400">Weighted Feasibility</div>
            <div className="text-4xl font-bold font-mono text-amber-400 mt-1">
              {judge.feasibility_score.toFixed(1)}
              <span className="text-base text-slate-500">/100</span>
            </div>
            <div className="text-xs text-slate-400 mt-1">
              Confidence: <strong className="text-slate-200">{(judge.confidence * 100).toFixed(0)}%</strong>
            </div>
            <div className="text-[11px] font-mono text-slate-500 mt-1">
              {judge.provider_used}:{judge.model_used}
            </div>
          </div>
        </div>
      </Card>

      {judge.hard_blockers.length > 0 && (
        <Card className="p-4 border-rose-500/40 bg-rose-950/20 space-y-2">
          <div className="flex items-center gap-2 text-rose-300 font-semibold text-sm">
            <AlertOctagon className="w-4 h-4" />
            <span>Critical Hard Blockers (Override High Averages)</span>
          </div>
          {judge.hard_blockers.map((hb) => (
            <div key={hb.blocker_id} className="text-xs text-rose-200 bg-rose-950/40 p-2.5 rounded border border-rose-500/20">
              <strong>[{hb.severity}] {hb.category}:</strong> {hb.description}
            </div>
          ))}
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <Card className="p-5 lg:col-span-2 space-y-4">
          <h3 className="text-sm font-semibold text-white">Topic-Adaptive 8-Dimension Weighted Scorecard</h3>
          <div className="space-y-3">
            {judge.scorecard.map((dim) => (
              <div key={dim.dimension} className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="font-medium text-slate-200">
                    {dim.label}{" "}
                    <span className="text-slate-500 font-mono">({(dim.weight * 100).toFixed(0)}%)</span>
                  </span>
                  <span className="font-mono text-amber-300">{dim.score.toFixed(0)}/100</span>
                </div>
                <div className="h-2 rounded-full bg-slate-800 overflow-hidden">
                  <div
                    className={`h-full ${
                      dim.score >= 70 ? "bg-emerald-400" : dim.score >= 50 ? "bg-amber-400" : "bg-rose-400"
                    }`}
                    style={{ width: `${dim.score}%` }}
                  />
                </div>
                <p className="text-[11px] text-slate-400">{dim.rationale}</p>
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-5 space-y-4">
          <h3 className="text-sm font-semibold text-white">Deterministic Verification Audit</h3>
          <div className="space-y-2 text-xs">
            {Object.entries(judge.deterministic_checks).map(([k, v]) => (
              <div key={k} className="flex justify-between py-1 border-b border-slate-800/70">
                <span className="text-slate-400">{k.replace(/_/g, " ")}</span>
                <span className="font-mono text-slate-200">{String(v)}</span>
              </div>
            ))}
          </div>

          {judge.preserved_minority_opinions.length > 0 && (
            <div className="pt-2">
              <h4 className="text-xs font-semibold uppercase text-indigo-300 mb-1.5">
                Preserved Minority Opinions
              </h4>
              <ul className="list-disc list-inside text-xs text-slate-300 space-y-1">
                {judge.preserved_minority_opinions.map((m, i) => (
                  <li key={i}>{m}</li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <Card className="p-5 space-y-3">
          <h3 className="text-sm font-semibold text-emerald-300 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" />
            <span>Strongest Arguments For &amp; Conditions</span>
          </h3>
          <ul className="list-disc list-inside text-xs text-slate-300 space-y-1.5">
            {judge.best_arguments_for.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
          {judge.conditions_for_approval.length > 0 && (
            <div className="pt-2 border-t border-slate-800">
              <div className="text-xs font-semibold text-amber-300 mb-1">Conditions Before Proceeding</div>
              <ul className="list-disc list-inside text-xs text-slate-300 space-y-1">
                {judge.conditions_for_approval.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </div>
          )}
        </Card>

        <Card className="p-5 space-y-3">
          <h3 className="text-sm font-semibold text-rose-300 flex items-center gap-2">
            <ShieldAlert className="w-4 h-4" />
            <span>Strongest Arguments Against &amp; Required Changes</span>
          </h3>
          <ul className="list-disc list-inside text-xs text-slate-300 space-y-1.5">
            {judge.strongest_arguments_against.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
          {judge.required_changes.length > 0 && (
            <div className="pt-2 border-t border-slate-800">
              <div className="text-xs font-semibold text-orange-300 mb-1">Required Modifications</div>
              <ul className="list-disc list-inside text-xs text-slate-300 space-y-1">
                {judge.required_changes.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      </div>

      {judge.roadmap.length > 0 && (
        <Card className="p-5 space-y-3">
          <h3 className="text-sm font-semibold text-white">Recommended Phased Implementation Roadmap</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {judge.roadmap.map((m, i) => (
              <div key={i} className="p-3.5 rounded-lg bg-slate-950 border border-slate-800 space-y-1.5">
                <div className="text-[11px] font-mono text-amber-400">{m.phase} · {m.owner_role}</div>
                <div className="text-sm font-semibold text-white">{m.title}</div>
                <p className="text-xs text-slate-300">{m.deliverable}</p>
                <div className="text-[11px] text-emerald-300">Gate: {m.acceptance_criterion}</div>
                {m.stop_condition && (
                  <div className="text-[11px] text-rose-300">Stop trigger: {m.stop_condition}</div>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
