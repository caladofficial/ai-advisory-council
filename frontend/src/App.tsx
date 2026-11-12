import React, { useState } from "react";
import { SidebarLayout, type NavRoute } from "./components/layout/SidebarLayout";
import { OverviewPage } from "./pages/OverviewPage";
import { NewInvestigationPage } from "./pages/NewInvestigationPage";
import { InvestigationWorkspacePage } from "./pages/InvestigationWorkspacePage";
import { ModelRegistryPage } from "./pages/ModelRegistryPage";
import { EvaluationLabPage } from "./pages/EvaluationLabPage";
import { SystemAuditPage } from "./pages/SystemAuditPage";

export function App() {
  const [route, setRoute] = useState<NavRoute>("overview");
  const [activeId, setActiveId] = useState<string | null>(null);

  const openWorkspace = (id: string) => {
    setActiveId(id);
    setRoute("workspace");
  };

  return (
    <SidebarLayout route={route} onNavigate={setRoute} activeInvestigationId={activeId}>
      {route === "overview" && (
        <OverviewPage
          onNewInvestigation={() => setRoute("new")}
          onOpenInvestigation={openWorkspace}
        />
      )}
      {route === "new" && <NewInvestigationPage onCreated={openWorkspace} />}
      {route === "workspace" && activeId && (
        <InvestigationWorkspacePage investigationId={activeId} />
      )}
      {route === "models" && <ModelRegistryPage />}
      {route === "evaluation" && <EvaluationLabPage />}
      {route === "audit" && <SystemAuditPage />}
    </SidebarLayout>
  );
}

export default App;
