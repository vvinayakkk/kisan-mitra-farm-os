import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown, Loader2, Pencil, RefreshCw, Sparkles, X } from "lucide-react";
import { workspaceRequest } from "@/lib/farmWorkspaceClient";
import { getAssistantSessionId, useAssistant } from "@/lib/assistantClient";
import { onWorkspaceCacheInvalidated } from "@/lib/workspaceCacheLifecycle";
import { WorkspaceVoiceField } from "@/components/WorkspaceVoiceField";
import { ResearchSources, type ResearchResult } from "./ResearchSources";
import "./prepared-by-saathi.css";
export type PreparationArea = "today" | "markets" | "schemes" | "records" | "crops" | "exchange";
interface Proposal { id: string; title: string; summary: string; steps: {title: string}[]; status: string; row_version: number; created_at: string; mission_id?: string; evidence: {label: string; detail?: string; url?: string}[]; research?: ResearchResult }
interface Snapshot { proposals: Proposal[]; job?: {state: string; safe_error?: string} }
export function PreparedBySaathi({area, active = true}: {area: PreparationArea; active?: boolean}) {
  const root = useRef<HTMLElement>(null);
  const {ready} = useAssistant();
  const [visible, setVisible] = useState(false), [data, setData] = useState<Snapshot | null>(null), [open, setOpen] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [editingProposal, setEditingProposal] = useState<Proposal | null>(null);
  const [editing, setEditing] = useState(false), [title, setTitle] = useState(""), [steps, setSteps] = useState("");
  const [revision, setRevision] = useState(0);
  const session = getAssistantSessionId();
  const mounted = useRef(false);
  const scope = useRef({session, area});
  scope.current = {session, area};
  const ownMutations = useRef(new Set<symbol>());
  const isCurrent = () => mounted.current && getAssistantSessionId() === session && scope.current.session === session && scope.current.area === area;
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; ownMutations.current.clear(); }; }, []);
  useEffect(() => { if (!root.current) return; if (typeof IntersectionObserver === "undefined") {setVisible(true);return;} const observer = new IntersectionObserver(entries => setVisible(entries.some(entry => entry.isIntersecting))); observer.observe(root.current); return () => observer.disconnect(); }, []);
  useEffect(() => { setData(null); setEditing(false); setEditingProposal(null); setError(""); setBusy(false); ownMutations.current.clear(); }, [session, area]);
  useEffect(() => onWorkspaceCacheInvalidated(reason => {
    if(reason === "session") {setData(null);setEditing(false);setEditingProposal(null);setBusy(false);ownMutations.current.clear();}


    else if (!ownMutations.current.size) setRevision(value => value+1);
  }), []);
  useEffect(() => {
    if (!active || !ready || !visible) return;
    let cancelled = false, timeout: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    const refresh = async () => {
      if (document.visibilityState === "hidden") { timeout=setTimeout(refresh, 5000); return; }
      try {
        let next = await workspaceRequest<Snapshot>(`/api/companion/proposals?area=${area}`, "GET", undefined, {signal: controller.signal, fresh: true});
        if (cancelled || !isCurrent()) return;
        if (!next.proposals.length && !next.job) {
          const mutation = Symbol("automatic preparation");
          ownMutations.current.add(mutation);
          try {
            const job = await workspaceRequest<NonNullable<Snapshot['job']>>("/api/companion/prepare", "POST", {area}, {signal: controller.signal});
            if(cancelled || !isCurrent()) return;
            next = {...next, job};
          } finally { ownMutations.current.delete(mutation); }
        }
        setData(next); setError("");
        timeout=setTimeout(refresh, next.job && ["queued","running"].includes(next.job.state) ? 2500 : 60_000);
      } catch(failure) { if(!cancelled && isCurrent()) {setError(failure instanceof Error ? failure.message : "Could not load suggestions."); timeout=setTimeout(refresh, 15_000);} }
    };
    void refresh();
    const visibleAgain = () => { if(document.visibilityState === "visible") setRevision(value => value+1); };
    document.addEventListener("visibilitychange", visibleAgain);
    return () => {cancelled=true; controller.abort();clearTimeout(timeout); document.removeEventListener("visibilitychange", visibleAgain);};
  }, [active, ready, visible, area, session, revision]);
  const item = editing && editingProposal ? editingProposal : data?.proposals[0];
  const working = data?.job && ["queued","running"].includes(data.job.state);
  async function prepare(research=false) {
    if (!isCurrent() || busy) return;
    const mutation = Symbol("preparation"); ownMutations.current.add(mutation);
    setBusy(true);setError("");
    try {
      await workspaceRequest("/api/companion/prepare", "POST", {area,research});
      if (isCurrent()) {setRevision(value=>value+1);setOpen(true);}
    } catch(failure) {if (isCurrent()) setError(failure instanceof Error ? failure.message : "Could not prepare suggestions.");}
    finally {ownMutations.current.delete(mutation);if (isCurrent()) setBusy(false);}
  }
  async function review(action: "approve"|"edit"|"dismiss") {
    if(!item || !isCurrent() || busy) return;
    const mutation = Symbol("proposal review"); ownMutations.current.add(mutation);
    setBusy(true);setError("");
    try {
      await workspaceRequest(`/api/companion/proposals/${item.id}/review`, "POST", {action,row_version:item.row_version,...(editing && action!=="dismiss" ? {title,steps:steps.split("\n").map(value=>value.trim()).filter(Boolean)}:{})});
      if (isCurrent()) {setEditing(false);setEditingProposal(null);setRevision(value=>value+1);}
    } catch(failure) {if (isCurrent()) setError(failure instanceof Error ? failure.message : "Could not review this plan.");}
    finally {ownMutations.current.delete(mutation);if (isCurrent()) setBusy(false);}
  }
  return <section ref={root} className="saathi-prepared" aria-label="Prepared by Saathi">
    <button type="button" className="saathi-prepared-heading" onClick={()=>setOpen(value=>!value)} aria-expanded={open}><Sparkles size={16}/><span><small>PREPARED BY SAATHI</small><strong>{working ? "Reviewing your farm…" : item?.title || "A little help with your next step"}</strong></span>{working ? <Loader2 size={16} className="spin"/> : <ChevronDown size={16} style={{transform:open ? "rotate(180deg)":undefined}}/>}</button>
    {open && <div className="saathi-prepared-body">
      {item ? <><p>{item.summary}</p>{editing ? <div className="saathi-plan-editor"><label>Plan title<input value={title} maxLength={160} onChange={event=>setTitle(event.target.value)}/></label><label>Steps, one per line<WorkspaceVoiceField label="Speak a plan step" onTranscript={text=>setSteps(value=>value ? `${value}\n${text}`:text)}><textarea rows={5} value={steps} onChange={event=>setSteps(event.target.value)} /></WorkspaceVoiceField></label></div> : <ol>{item.steps.map((step,index)=><li key={index}>{step.title}</li>)}</ol>}
      {!!item.evidence.length && <details><summary>Based on your records · {item.evidence.length}</summary><ul className="saathi-evidence">{item.evidence.map((e,index)=><li key={index}><strong>{e.label}</strong>{e.detail && <span>{e.detail}</span>}{e.url && /^https?:\/\//.test(e.url) && <a href={e.url} target="_blank" rel="noopener noreferrer">Official source</a>}</li>)}</ul></details>}
      {item.research?.preparation?.translation_status === "unavailable" && <small>Translation is unavailable right now. This draft is in English.</small>}
      {item.research && item.research.status !== "not_requested" && <ResearchSources result={item.research}/>}
      <div className="saathi-proposal-actions">{item.status==='approved' ? <a href="/workspace?view=records&tab=missions"><Check size={14}/> Saved to your plans</a> : <><button disabled={busy||!!working} onClick={()=>void review('approve')}><Check size={14}/> Approve plan</button>{editing ? <><button disabled={busy} onClick={()=>void review('edit')}>Save edits</button><button disabled={busy} onClick={()=>setEditing(false)}>Cancel</button></> : <button disabled={busy} onClick={()=>{setEditingProposal(item);setTitle(item.title);setSteps(item.steps.map(s=>s.title).join('\n'));setEditing(true);}}><Pencil size={13}/> Edit</button>}<button disabled={busy} onClick={()=>void review('dismiss')}><X size={13}/> Dismiss</button></>}</div><small>Prepared {new Date(item.created_at).toLocaleDateString()} · Approval saves a plan in your notebook.</small></> : <p>{working ? "Pulling together the relevant records. You can keep using this page." : "Prepare a useful next step from your farm records."}</p>}
      <div className="saathi-prepare-actions"><button disabled={busy||!!working} onClick={()=>void prepare()}><RefreshCw size={13}/> Refresh</button>{['markets','schemes'].includes(area) && <button disabled={busy||!!working} onClick={()=>void prepare(true)}><Sparkles size={13}/> Research the web</button>}</div>
      {data?.job?.state==='failed' && <p role="alert">Preparation was interrupted. Refresh to try again.</p>}
    </div>}{error && <p className="saathi-prepared-error" role="alert">{error}</p>}
  </section>;
}
