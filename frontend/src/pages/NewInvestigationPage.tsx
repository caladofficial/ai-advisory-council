import React, { useState } from "react";
import { Play, Sparkles } from "lucide-react";
import { api } from "../services/api";
import { Card } from "../components/ui/Badges";

interface NewInvestigationPageProps {
  onCreated: (investigationId: string) => void;
}

const CONNECTORS = [
  { id: "openalex", label: "OpenAlex (Papers)" },
  { id: "crossref", label: "Crossref (DOIs)" },
  { id: "arxiv", label: "arXiv (Preprints)" },
  { id: "github", label: "GitHub REST (Repos)" },
  { id: "huggingface", label: "Hugging Face Hub" },
  { id: "wikipedia", label: "Wikipedia (Context)" },
  { id: "web_search", label: "Web Search & Crawler" },
];

export function NewInvestigationPage({ onCreated }: NewInvestigationPageProps) {
  const [topic, setTopic] = useState("");
  const [objective, setObjective] = useState("Evaluate technical, economic, legal, and operational feasibility");
  const [mode, setMode] = useState("general_decision");
  const [executionProfile, setExecutionProfile] = useState("full_10_plus_1");
  const [geography, setGeography] = useState("Global");
  const [timeHorizon, setTimeHorizon] = useState("12 months");
  const [budget, setBudget] = useState("");
  const [targetUsers, setTargetUsers] = useState("");
  const [constraintsText, setConstraintsText] = useState("");
  const [connectors, setConnectors] = useState<string[]>(CONNECTORS.map((c) => c.id));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const toggleConnector = (id: string) => {
    setConnectors((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const handleSubmit = async (e: React.FormEvent, autoStart: boolean) => {
    e.preventDefault();
    if (topic.trim().length < 5) {
      setError("Please describe your topic or proposal (at least 5 characters).");
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      const inv = await api.createInvestigation({
        topic: topic.trim(),
        objective: objective.trim(),
        mode,
        execution_profile: executionProfile,
        geography: geography.trim() || "Global",
        time_horizon: timeHorizon.trim() || "12 months",
        budget: budget.trim(),
        target_users: targetUsers.trim(),
        constraints: constraintsText
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
        enabled_connectors: connectors,
        auto_start: autoStart,
      });
      onCreated(inv.investigation_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create investigation");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="font-editorial text-3xl text-white">New Council Investigation</h1>
        <p className="text-sm text-slate-400 mt-1">
          Submit an idea, architecture, startup plan, or research hypothesis. The system researches sources first, passes the Readiness Gate, and convenes the council.
        </p>
      </div>

      <form onSubmit={(e) => handleSubmit(e, true)}>
        <Card className="p-6 space-y-5">
          {error && (
            <div className="p-3 rounded-lg bg-rose-500/15 border border-rose-500/40 text-xs text-rose-300">
              {error}
            </div>
          )}

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                Proposal, Idea, or Decision Question *
              </label>
              <button
                type="button"
                onClick={() => {
                  setTopic("Build an offline-capable AI tutoring platform for rural secondary schools in India");
                  setBudget("INR 500000");
                  setGeography("India");
                  setTargetUsers("Rural Grade 8-12 students and school teachers");
                  setMode("business_feasibility");
                }}
                className="text-xs text-amber-400 hover:text-amber-300 inline-flex items-center gap-1 cursor-pointer"
              >
                <Sparkles className="w-3 h-3" />
                <span>Load Example Topic</span>
              </button>
            </div>
            <textarea
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              rows={3}
              placeholder="e.g. Evaluate building a local-first AI healthcare triage assistant for rural clinics..."
              className="w-full rounded-lg bg-slate-950 border border-slate-800 focus:border-amber-500 focus:outline-none p-3 text-sm text-white"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                Investigation Mode (Adapts Judge Weights)
              </label>
              <select
                value={mode}
                onChange={(e) => setMode(e.target.value)}
                className="w-full rounded-lg bg-slate-950 border border-slate-800 p-2.5 text-sm text-white"
              >
                <option value="general_decision">General Decision Analysis</option>
                <option value="business_feasibility">Business Feasibility</option>
                <option value="technical_feasibility">Technical Feasibility</option>
                <option value="scientific_research">Scientific Research</option>
                <option value="product_evaluation">Product Evaluation</option>
                <option value="policy_analysis">Policy &amp; Regulatory Analysis</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                Council Execution Profile
              </label>
              <select
                value={executionProfile}
                onChange={(e) => setExecutionProfile(e.target.value)}
                className="w-full rounded-lg bg-slate-950 border border-slate-800 p-2.5 text-sm text-white"
              >
                <option value="full_10_plus_1">Full Council (10 Advisors + 1 Chief Judge)</option>
                <option value="prototype_3_plus_1">Fast Prototype (Tech + Finance + Devil's Advocate + Judge)</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                Geography / Jurisdiction
              </label>
              <input
                value={geography}
                onChange={(e) => setGeography(e.target.value)}
                className="w-full rounded-lg bg-slate-950 border border-slate-800 p-2.5 text-sm text-white"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                Budget Ceiling (Optional)
              </label>
              <input
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
                placeholder="e.g. $5,000 or INR 5 Lakh"
                className="w-full rounded-lg bg-slate-950 border border-slate-800 p-2.5 text-sm text-white"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                Time Horizon
              </label>
              <input
                value={timeHorizon}
                onChange={(e) => setTimeHorizon(e.target.value)}
                className="w-full rounded-lg bg-slate-950 border border-slate-800 p-2.5 text-sm text-white"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                Target Users / Stakeholders
              </label>
              <input
                value={targetUsers}
                onChange={(e) => setTargetUsers(e.target.value)}
                placeholder="Who will use or be affected by this?"
                className="w-full rounded-lg bg-slate-950 border border-slate-800 p-2.5 text-sm text-white"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                Primary Objective
              </label>
              <input
                value={objective}
                onChange={(e) => setObjective(e.target.value)}
                className="w-full rounded-lg bg-slate-950 border border-slate-800 p-2.5 text-sm text-white"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
              Hard Constraints (one per line)
            </label>
            <textarea
              value={constraintsText}
              onChange={(e) => setConstraintsText(e.target.value)}
              rows={2}
              placeholder="Must run offline&#10;Must comply with DPDP / GDPR&#10;Zero paid LLM licenses"
              className="w-full rounded-lg bg-slate-950 border border-slate-800 p-2.5 text-sm text-white"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
              Centralized Research Engine Connectors
            </label>
            <div className="flex flex-wrap gap-2">
              {CONNECTORS.map((c) => {
                const active = connectors.includes(c.id);
                return (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => toggleConnector(c.id)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium border cursor-pointer transition-colors ${
                      active
                        ? "bg-sky-500/15 border-sky-500/40 text-sky-300"
                        : "bg-slate-950 border-slate-800 text-slate-500"
                    }`}
                  >
                    {c.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-end gap-3 pt-3 border-t border-slate-800">
            <button
              type="button"
              disabled={submitting}
              onClick={(e) => handleSubmit(e, false)}
              className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-sm font-medium text-slate-200 cursor-pointer"
            >
              Create Draft (Upload Docs First)
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-5 py-2.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 text-sm font-semibold inline-flex items-center gap-2 shadow-lg shadow-amber-500/20 cursor-pointer"
            >
              <Play className="w-4 h-4" />
              <span>{submitting ? "Launching..." : "Launch Investigation"}</span>
            </button>
          </div>
        </Card>
      </form>
    </div>
  );
}
