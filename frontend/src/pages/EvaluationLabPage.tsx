import React, { useState } from "react";
import { CheckCircle2, FlaskConical, Play, XCircle } from "lucide-react";
import { api } from "../services/api";
import type { BenchmarkRun } from "../types";
import { Card } from "../components/ui/Badges";

export function EvaluationLabPage() {
  const [run, setRun] = useState<BenchmarkRun | null>(null);
  const [includeLive, setIncludeLive] = useState(false);
  const [running, setRunning] = useState(false);

  const handleRun = async () => {
    setRunning(true);
    try {
      setRun(await api.runBenchmarks(includeLive));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-editorial text-3xl text-white">Model &amp; Guardrail Evaluation Lab</h1>
          <p className="text-sm text-slate-400 mt-1">
            Verify zero-paid enforcement, SSRF &amp; prompt-injection defenses, syndication deduplication, citation audit flags, and deterministic financial calculations.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <label className="inline-flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={includeLive}
              onChange={(e) => setIncludeLive(e.target.checked)}
              className="rounded border-slate-700"
            />
            <span>Include Live Model Probe</span>
          </label>
          <button
            type="button"
            disabled={running}
            onClick={handleRun}
            className="px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-semibold inline-flex items-center gap-2 cursor-pointer"
          >
            <Play className="w-3.5 h-3.5" />
            <span>{running ? "Running..." : "Run Evaluation Suite"}</span>
          </button>
        </div>
      </div>

      {!run ? (
        <Card className="p-10 text-center space-y-2">
          <FlaskConical className="w-10 h-10 text-slate-600 mx-auto" />
          <div className="text-sm font-medium text-slate-300">Ready to run system benchmarks</div>
          <p className="text-xs text-slate-500">Click "Run Evaluation Suite" to execute automated verification checks.</p>
        </Card>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Card className="p-4">
              <div className="text-xs text-slate-400">Run ID</div>
              <div className="font-mono text-lg text-white mt-1">{run.run_id}</div>
            </Card>
            <Card className="p-4">
              <div className="text-xs text-slate-400">Cases Passed</div>
              <div className="font-mono text-lg text-emerald-300 mt-1">
                {run.passed_cases} / {run.total_cases}
              </div>
            </Card>
            <Card className="p-4">
              <div className="text-xs text-slate-400">Overall Score</div>
              <div className="font-mono text-lg text-amber-400 mt-1">{run.overall_score}%</div>
            </Card>
          </div>

          <Card className="p-5 space-y-2.5">
            {run.results.map((r) => (
              <div key={r.case_id} className="p-3.5 rounded-lg bg-slate-950 border border-slate-800 flex items-start justify-between gap-4">
                <div className="flex items-start gap-2.5">
                  {r.passed ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
                  ) : (
                    <XCircle className="w-4 h-4 text-rose-400 mt-0.5 shrink-0" />
                  )}
                  <div>
                    <div className="text-xs font-semibold text-white">
                      <span className="font-mono text-slate-400 mr-2">{r.case_id}</span>
                      {r.name}
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">{r.details}</p>
                  </div>
                </div>
                <span className="font-mono text-xs text-amber-300 shrink-0">{r.score}%</span>
              </div>
            ))}
          </Card>
        </div>
      )}
    </div>
  );
}
