import { useEffect, useId, useRef, useState } from "react";
import { Check, ChevronDown, ExternalLink, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { workspaceRequest } from "@/lib/farmWorkspaceClient";
import { getAssistantSessionId } from "@/lib/assistantClient";
import { ResearchSources, type ResearchResult } from "./ResearchSources";

export interface CompanionProposalData {
  id: string; area: string; title: string; summary: string;
  steps: { title: string }[]; evidence: { label: string; detail?: string; url?: string }[];
  research?: ResearchResult; status: string; row_version: number; mission_id?: string;
}
export const preparedAreas: Record<string, { view: string; label: string }> = {
  today: { view: "records", label: "Farm notebook" }, records: { view: "records", label: "Farm notebook" },
  markets: { view: "markets", label: "Mandi compass" }, schemes: { view: "schemes", label: "Farm support" },
  crops: { view: "crops", label: "Crop doctor" }, exchange: { view: "exchange", label: "Farmer exchange" },
};
export function CompanionProposal({ item, onReviewed, onNavigate }: {
  item: CompanionProposalData; onReviewed: (proposal: CompanionProposalData) => void; onNavigate: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef(false), mounted = useRef(true);
  const id = useId();
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const area = preparedAreas[item.area];
  const saved = item.status === "approved";
  const planHref = `/workspace?view=records&tab=missions&mission=${encodeURIComponent(item.mission_id || "")}`;
  async function approve() {
    if (pending.current || saved) return;
    pending.current = true; setBusy(true); setError("");
    const session = getAssistantSessionId();
    try {
      const result = await workspaceRequest<{ proposal: CompanionProposalData; mission_id: string }>(
        `/api/companion/proposals/${item.id}/review`, "POST", { action: "approve", row_version: item.row_version },
      );
      if (getAssistantSessionId() !== session) return;
      if (result.proposal.status !== "approved" || !result.mission_id) throw new Error("Your plan could not be confirmed. Try again.");
      if (mounted.current) onReviewed(result.proposal);
      toast.success("Plan saved to your notebook", { description: result.proposal.title });
    } catch (failure) {
      if (getAssistantSessionId() === session) {
        const message = failure instanceof Error ? failure.message : "Could not save this plan. Try again.";
        if (mounted.current) setError(message);
        toast.error("Plan not saved", { description: message });
      }
    } finally { pending.current = false; if (mounted.current) setBusy(false); }
  }
  return <article className={`saathi-review-item${saved ? " is-saved" : ""}`}>
    <button className="saathi-review-toggle" aria-expanded={expanded} aria-controls={id} onClick={() => setExpanded(value => !value)}>
      <span><small>{area.label}</small><strong>{item.title}</strong></span>
      <ChevronDown size={15} style={{ transform: expanded ? "rotate(180deg)" : undefined }} />
    </button>
    {expanded && <div id={id} className="saathi-review-preview">
      <p>{item.summary}</p>
      <ol>{item.steps.map((step, index) => <li key={index}>{step.title}</li>)}</ol>
      {!!item.evidence?.length && <details><summary>Based on your records</summary>{item.evidence.map((source, index) => <p key={index}><strong>{source.label}</strong>{source.detail && <span>{source.detail}</span>}{source.url && /^https?:\/\//i.test(source.url) && <a href={source.url} target="_blank" rel="noopener noreferrer">View source</a>}</p>)}</details>}
      {item.research && item.research.status !== "not_requested" && <ResearchSources result={item.research} />}
      <a className="saathi-review-area" href={`/workspace?view=${area.view}`} onClick={onNavigate}>Open {area.label}<ExternalLink size={12}/></a>
    <div className="saathi-review-actions">
      {saved ? <><span role="status"><Check size={13}/> Plan saved</span><a href={planHref} onClick={onNavigate}>View plan <ExternalLink size={12}/></a></> : <>
        <small>{item.steps.length} steps · saves to notebook</small>
        <button disabled={busy} onClick={() => void approve()} aria-label={`Approve and save ${item.title}`}>{busy ? <Loader2 size={13} className="spin"/> : <Check size={13}/>} {busy ? "Saving…" : "Approve & save plan"}</button>
      </>}
    </div>
    {error && <p className="saathi-review-error" role="alert">{error}</p>}
    </div>}
  </article>;
}
