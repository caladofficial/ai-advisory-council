import React, { useState } from "react";
import { ArrowRight, GitCompare, MessageSquare } from "lucide-react";
import type { DebateTranscript } from "../../types";
import { Card, EvidenceChip, StatusBadge } from "../ui/Badges";

interface DebateTimelineProps {
  debate: DebateTranscript;
  onSelectEvidence: (evdId: string) => void;
}

export function DebateTimeline({ debate, onSelectEvidence }: DebateTimelineProps) {
  const [roundFilter, setRoundFilter] = useState<number>(0);

  const visibleMessages =
    roundFilter === 0
      ? debate.messages
      : debate.messages.filter((m) => m.round_number === roundFilter);

  return (
    <div className="space-y-6">
      <Card className="p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <GitCompare className="w-4 h-4 text-amber-400" />
            <h3 className="text-sm font-semibold text-white">
              Moderator Challenge Graph (Prioritized by P = Impact × Uncertainty × Relevance)
            </h3>
          </div>
          <span className="text-xs text-slate-400 font-mono">
            {debate.challenges.length} targeted challenge(s)
          </span>
        </div>

        {debate.challenges.length === 0 ? (
          <p className="text-xs text-slate-500">Challenges will appear once Stage-6 debate preparation runs.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {debate.challenges.map((ch) => (
              <div key={ch.challenge_id} className="p-3.5 rounded-lg bg-slate-950 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 text-xs font-mono text-white">
                    <span className="text-amber-300">{ch.challenger_id}</span>
                    <ArrowRight className="w-3.5 h-3.5 text-slate-500" />
                    <span className="text-sky-300">{ch.target_advisor_id}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 font-mono text-[11px]">
                      P={ch.priority_score} ({ch.impact_score}×{ch.uncertainty_score}×{ch.relevance_score})
                    </span>
                    <StatusBadge status={ch.disposition || ch.status} />
                  </div>
                </div>
                <p className="text-xs text-slate-200">{ch.challenge_argument}</p>
                <div className="text-[11px] text-slate-400">
                  Target claim: <span className="font-mono text-slate-300">{ch.target_claim_id}</span> — {ch.requested_action}
                </div>
                {ch.evidence_ids.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {ch.evidence_ids.map((eid) => (
                      <EvidenceChip key={eid} id={eid} onClick={onSelectEvidence} />
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card className="p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <MessageSquare className="w-4 h-4 text-sky-400" />
            <h3 className="text-sm font-semibold text-white">Structured Debate Transcript</h3>
          </div>
          <div className="flex items-center gap-1.5">
            {[
              { id: 0, label: "All Rounds" },
              { id: 1, label: "R1 Openings" },
              { id: 2, label: "R2 Challenges" },
              { id: 3, label: "R3 Rebuttals" },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setRoundFilter(tab.id)}
                className={`px-2.5 py-1 rounded text-xs font-medium cursor-pointer transition-colors ${
                  roundFilter === tab.id
                    ? "bg-amber-500 text-slate-950 font-semibold"
                    : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-3">
          {visibleMessages.map((msg) => (
            <div key={msg.message_id} className="p-3.5 rounded-lg bg-slate-950 border border-slate-800/90 space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-xs">
                  <span className="px-1.5 py-0.5 rounded bg-slate-800 font-mono text-slate-300">
                    R{msg.round_number} · {msg.message_type}
                  </span>
                  <span className="font-semibold text-white">{msg.sender}</span>
                  {msg.receiver !== "council" && (
                    <>
                      <ArrowRight className="w-3 h-3 text-slate-500" />
                      <span className="text-sky-300">{msg.receiver}</span>
                    </>
                  )}
                </div>
                <div className="flex items-center gap-1.5">
                  {msg.disposition && <StatusBadge status={msg.disposition} />}
                  {msg.position_change && (
                    <span className="text-[11px] font-mono text-amber-300">{msg.position_change}</span>
                  )}
                </div>
              </div>
              <p className="text-xs text-slate-200 whitespace-pre-wrap leading-relaxed">{msg.argument}</p>
              <div className="flex flex-wrap items-center gap-1.5">
                {msg.evidence_ids.map((eid) => (
                  <EvidenceChip key={eid} id={eid} onClick={onSelectEvidence} />
                ))}
                {msg.unverified_evidence_ids.length > 0 && (
                  <span className="text-[11px] text-rose-400 font-mono">
                    Flagged unverified: {msg.unverified_evidence_ids.join(", ")}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
