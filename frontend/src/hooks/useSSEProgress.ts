import { useEffect, useState } from "react";
import { api } from "../services/api";

export interface LiveProgress {
  status: string;
  stage: string;
  progress_percent: number;
  message: string;
  advisor_statuses: Record<string, string>;
  timestamp: string;
}

export function useSSEProgress(investigationId: string | null, active: boolean) {
  const [live, setLive] = useState<LiveProgress | null>(null);

  useEffect(() => {
    if (!investigationId || !active) return;

    const es = new EventSource(api.sseProgressUrl(investigationId));
    const onProgress = (ev: MessageEvent) => {
      try {
        const parsed = JSON.parse(ev.data) as LiveProgress;
        setLive(parsed);
      } catch {
        // Ignore malformed frame
      }
    };
    es.addEventListener("progress", onProgress);

    return () => {
      es.removeEventListener("progress", onProgress);
      es.close();
    };
  }, [investigationId, active]);

  return live;
}
