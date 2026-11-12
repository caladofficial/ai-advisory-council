import React from "react";
import {
  Activity,
  Cpu,
  FlaskConical,
  LayoutDashboard,
  PlusCircle,
  Scale,
  ShieldCheck,
} from "lucide-react";

export type NavRoute = "overview" | "new" | "workspace" | "models" | "evaluation" | "audit";

interface SidebarLayoutProps {
  route: NavRoute;
  onNavigate: (r: NavRoute) => void;
  activeInvestigationId?: string | null;
  children: React.ReactNode;
}

export function SidebarLayout({
  route,
  onNavigate,
  activeInvestigationId,
  children,
}: SidebarLayoutProps) {
  const navItems: Array<{ id: NavRoute; label: string; icon: React.ReactNode; hidden?: boolean }> = [
    { id: "overview", label: "Overview", icon: <LayoutDashboard className="w-4 h-4" /> },
    { id: "new", label: "New Investigation", icon: <PlusCircle className="w-4 h-4" /> },
    {
      id: "workspace",
      label: activeInvestigationId ? `Council (${activeInvestigationId})` : "Workspace",
      icon: <Scale className="w-4 h-4" />,
      hidden: !activeInvestigationId,
    },
    { id: "models", label: "Models & Free APIs", icon: <Cpu className="w-4 h-4" /> },
    { id: "evaluation", label: "Evaluation Lab", icon: <FlaskConical className="w-4 h-4" /> },
    { id: "audit", label: "System Audit", icon: <Activity className="w-4 h-4" /> },
  ];

  return (
    <div className="min-h-screen flex bg-slate-950 text-slate-100">
      <aside className="w-64 shrink-0 border-r border-slate-800/80 bg-slate-950/90 flex flex-col justify-between">
        <div>
          <div className="p-5 border-b border-slate-800/80">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center shadow-lg shadow-amber-500/20">
                <Scale className="w-5 h-5 text-slate-950" />
              </div>
              <div>
                <h1 className="font-semibold text-sm tracking-tight text-white">AI Advisory Council</h1>
                <p className="text-[11px] text-slate-400">10 Advisors + 1 Chief Judge</p>
              </div>
            </div>
          </div>

          <nav className="p-3 space-y-1">
            {navItems
              .filter((n) => !n.hidden)
              .map((item) => {
                const active = route === item.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => onNavigate(item.id)}
                    className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors cursor-pointer ${
                      active
                        ? "bg-amber-500/15 text-amber-300 border border-amber-500/30"
                        : "text-slate-400 hover:text-slate-100 hover:bg-slate-900"
                    }`}
                  >
                    {item.icon}
                    <span className="truncate">{item.label}</span>
                  </button>
                );
              })}
          </nav>
        </div>

        <div className="p-4 border-t border-slate-800/80 space-y-2.5">
          <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/25 p-3">
            <div className="flex items-center gap-1.5 text-emerald-300 text-xs font-semibold">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Zero-Paid Mode Active</span>
            </div>
            <p className="text-[11px] text-slate-400 mt-1">
              Local Ollama &amp; verified free APIs only. Credit-card fallback blocked.
            </p>
          </div>
        </div>
      </aside>

      <main className="flex-1 min-w-0 overflow-x-hidden">
        <div className="max-w-7xl mx-auto p-6 md:p-8">{children}</div>
      </main>
    </div>
  );
}
