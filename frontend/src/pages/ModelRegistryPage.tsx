import React, { useEffect, useState } from "react";
import { Activity, CheckCircle2, KeyRound, RefreshCw, ShieldCheck } from "lucide-react";
import { api } from "../services/api";
import type { ModelEntry, ProviderInfo } from "../types";
import { Card, StatusBadge } from "../components/ui/Badges";

export function ModelRegistryPage() {
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [models, setModels] = useState<ModelEntry[]>([]);
  const [profiles, setProfiles] = useState<Array<{ advisor_id: string; name: string; role: string }>>([]);
  const [assignments, setAssignments] = useState<Record<string, { provider: string; model_id: string }>>({});
  const [selectedProvider, setSelectedProvider] = useState("");
  const [keyInput, setKeyInput] = useState<Record<string, string>>({});
  const [busyMsg, setBusyMsg] = useState("");

  const load = async () => {
    const [p, m, prof, asgn] = await Promise.all([
      api.getProviders(),
      api.getModels(selectedProvider),
      api.getAdvisorProfiles(),
      api.getAdvisorAssignments(),
    ]);
    setProviders(p);
    setModels(m);
    setProfiles([...prof, { advisor_id: "chief_judge", name: "Independent Chief Judge", role: "Final Verdict" }]);
    setAssignments(asgn);
  };

  useEffect(() => {
    load();
  }, [selectedProvider]);

  const handleSaveKey = async (providerId: string) => {
    const val = keyInput[providerId]?.trim();
    if (!val) return;
    setBusyMsg(`Saving server-side key for ${providerId}...`);
    await api.configureProviderKey(providerId, val);
    setKeyInput((prev) => ({ ...prev, [providerId]: "" }));
    await load();
    setBusyMsg(`Configured ${providerId} cleanly (stored server-side only).`);
  };

  const handleHealthCheck = async () => {
    setBusyMsg("Probing local Ollama and configured free API endpoints...");
    await api.healthCheckModels();
    await load();
    setBusyMsg("Health check completed.");
  };

  const handleSync = async () => {
    setBusyMsg("Syncing Ollama, awesome-freellm-apis catalog, and Hugging Face Hub...");
    const res = await api.syncModels(true);
    await load();
    setBusyMsg(`Synced registry (+${res.synced_new_models} models).`);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="font-editorial text-3xl text-white">Model Registry &amp; Free API Hub</h1>
          <p className="text-sm text-slate-400 mt-1">
            Bundled 31+ free providers from <code className="text-amber-300">awesome-freellm-apis</code>, Hugging Face Inference Providers, and local Ollama.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={handleSync}
            className="px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 inline-flex items-center gap-1.5 cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Sync Ollama + HF Hub</span>
          </button>
          <button
            type="button"
            onClick={handleHealthCheck}
            className="px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-semibold inline-flex items-center gap-1.5 cursor-pointer"
          >
            <Activity className="w-3.5 h-3.5" />
            <span>Run Live Health Checks</span>
          </button>
        </div>
      </div>

      {busyMsg && (
        <div className="p-3 rounded-lg bg-sky-500/10 border border-sky-500/30 text-xs text-sky-300">
          {busyMsg}
        </div>
      )}

      <Card className="p-4 border-emerald-500/30 bg-emerald-950/15 flex items-center gap-3 text-xs text-emerald-200">
        <ShieldCheck className="w-5 h-5 text-emerald-400 shrink-0" />
        <span>
          <strong>Strict Zero-Paid Policy Enforced:</strong> Paid endpoints and credit-card fallback are blocked server-side. OpenRouter routes require <code>:free</code> suffix.
        </span>
      </Card>

      <Card className="p-5 space-y-4">
        <h2 className="text-sm font-semibold text-white">Free Providers Directory ({providers.length})</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {providers.slice(0, 15).map((p) => (
            <div key={p.provider_id} className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-sm text-white">{p.display_name}</span>
                {p.has_key_configured ? (
                  <span className="inline-flex items-center gap-1 text-[11px] text-emerald-300 font-mono">
                    <CheckCircle2 className="w-3 h-3" /> Ready ({p.masked_key})
                  </span>
                ) : (
                  <span className="text-[11px] text-slate-500">No key set</span>
                )}
              </div>
              <p className="text-[11px] text-slate-400 line-clamp-2">{p.tagline}</p>
              <div className="text-[11px] font-mono text-slate-400">
                Today: {p.requests_today}/{p.default_rpd} RPD · {p.default_rpm} RPM
              </div>
              {p.provider_id !== "ollama" && (
                <div className="flex gap-1.5 pt-1">
                  <input
                    type="password"
                    value={keyInput[p.provider_id] || ""}
                    onChange={(e) => setKeyInput((prev) => ({ ...prev, [p.provider_id]: e.target.value }))}
                    placeholder="Paste free API key..."
                    className="flex-1 rounded bg-slate-900 border border-slate-800 px-2 py-1 text-xs text-white"
                  />
                  <button
                    type="button"
                    onClick={() => handleSaveKey(p.provider_id)}
                    className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-[11px] text-amber-300 inline-flex items-center gap-1 cursor-pointer"
                  >
                    <KeyRound className="w-3 h-3" /> Save
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      </Card>

      <Card className="p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">Per-Seat Model Assignment (Diversity Control)</h2>
          <span className="text-xs text-slate-400">Assign distinct free model families per council seat</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {profiles.map((prof) => {
            const current = assignments[prof.advisor_id];
            return (
              <div key={prof.advisor_id} className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-between gap-2 text-xs">
                <div>
                  <div className="font-semibold text-white">{prof.name}</div>
                  <div className="text-[11px] text-slate-400">{prof.role}</div>
                </div>
                <select
                  value={current ? `${current.provider}::${current.model_id}` : ""}
                  onChange={async (e) => {
                    if (!e.target.value) return;
                    const [prov, mid] = e.target.value.split("::");
                    await api.assignAdvisorModel(prof.advisor_id, prov, mid);
                    await load();
                  }}
                  className="rounded bg-slate-900 border border-slate-800 px-2 py-1.5 text-xs text-slate-200 max-w-56"
                >
                  <option value="">Auto Router Priority</option>
                  {models.slice(0, 60).map((m) => (
                    <option key={m.id} value={`${m.provider}::${m.model_id}`}>
                      {m.provider}: {m.model_id}
                    </option>
                  ))}
                </select>
              </div>
            );
          })}
        </div>
      </Card>

      <Card className="p-5 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold text-white">Registered Free Models ({models.length})</h2>
          <select
            value={selectedProvider}
            onChange={(e) => setSelectedProvider(e.target.value)}
            className="rounded bg-slate-950 border border-slate-800 px-2.5 py-1.5 text-xs text-slate-200"
          >
            <option value="">All Providers</option>
            {providers.map((p) => (
              <option key={p.provider_id} value={p.provider_id}>{p.display_name}</option>
            ))}
          </select>
        </div>

        <div className="overflow-x-auto max-h-96 overflow-y-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-slate-400 border-b border-slate-800">
              <tr>
                <th className="py-2 pr-3">Provider</th>
                <th className="py-2 pr-3">Model ID</th>
                <th className="py-2 pr-3">Context</th>
                <th className="py-2 pr-3">Status</th>
                <th className="py-2">Latency</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/70">
              {models.slice(0, 120).map((m) => (
                <tr key={m.id}>
                  <td className="py-2 pr-3 font-mono text-slate-300">{m.provider}</td>
                  <td className="py-2 pr-3 font-mono text-white">{m.model_id}</td>
                  <td className="py-2 pr-3 font-mono text-slate-400">{m.context_window ? m.context_window.toLocaleString() : "—"}</td>
                  <td className="py-2 pr-3"><StatusBadge status={m.availability_status} /></td>
                  <td className="py-2 font-mono text-slate-400">{m.latency_ms ? `${m.latency_ms.toFixed(0)}ms` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
