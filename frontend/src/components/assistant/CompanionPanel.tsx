import { GuidedTour } from "@/components/tour/GuidedTour";
import { companionTour } from "@/components/tour/tours";
import { useEffect, useRef, useState } from "react";
import { AudioLines, Check, ChevronRight, FileText, Loader2, MessageCircle, Moon, Pause, Play, Settings2, Sparkles, Sprout, X } from "lucide-react";
import { apiFetch } from "@/lib/apiClient";
import { downloadArtifact, useAssistant } from "@/lib/assistantClient";
import { CompanionProposal, preparedAreas, type CompanionProposalData } from "./CompanionProposal";
import "./companion.css";

interface Preferences { row_version: number; name: string; enabled: boolean; frequency_hours: number; quiet_start: number; quiet_end: number; timezone: string }
interface Companion { prepared?: CompanionProposalData[]; name: string; status: string; worker_last_seen_at?: string; settings: Preferences; activity: { id: string; title?: string; detail?: string; created_at: string; status: string; href?: string }[]; channels: { in_app: { connected: boolean }; whatsapp: { connected: boolean; configured?: boolean; trial_limited?: boolean; masked_number?: string; enabled?: boolean; last_seen_at?: string } }; scope: string[] }
const base = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
const statusLabels: Record<string, string> = { paused: "Follow-ups paused", quiet_hours: "Quiet hours", watching: "Keeping an eye on your farm", waiting_for_worker: "Waiting to reconnect" };
export function CompanionAvatar({ small = false }: { small?: boolean }) {
  return <span className={`saathi-avatar ${small ? "small" : ""}`} aria-hidden="true"><Sprout/><span className="saathi-eyes"><i/><i/></span></span>;
}
export function CompanionPanel({ open, onClose, onVoice }: { open: boolean; onClose: () => void; onVoice: () => void }) {
  const [data, setData] = useState<Companion | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [link, setLink] = useState<{message:string;url:string;expires_in_seconds:number} | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Preferences | null>(null);
  const { artifacts } = useAssistant();
  const close = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    const controller = new AbortController();
    const refresh = async () => {
      if (document.visibilityState === "hidden") return;
      try {
        const response = await apiFetch(`${base}/api/companion`, { signal: controller.signal, cache: "no-store" });
        if (!response.ok) throw new Error("Saathi could not connect. Try again shortly.");
        const next = await response.json();
        if (!cancelled) { setData(next); setError(""); }
      } catch (failure) { if (!cancelled) setError(failure instanceof Error ? failure.message : "Connection unavailable."); }
    };
    void refresh(); close.current?.focus();
    const interval = setInterval(refresh, 30_000);
    document.addEventListener("visibilitychange", refresh);
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    document.addEventListener("keydown", escape);
    return () => { cancelled = true; controller.abort(); clearInterval(interval); document.removeEventListener("visibilitychange", refresh); document.removeEventListener("keydown", escape); };
  }, [open]);
  async function save(settings: Preferences) {
    setBusy(true); setError("");
    try {
      const response = await apiFetch(`${base}/api/companion/preferences`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ row_version: settings.row_version, name: settings.name, enabled: settings.enabled, frequency_hours: settings.frequency_hours, quiet_start: settings.quiet_start, quiet_end: settings.quiet_end, timezone: settings.timezone }) });
      const next = await response.json();
      if (!response.ok) throw new Error(typeof next.detail === "string" ? next.detail : "Settings could not be saved.");
      setData(next); setEditing(false);
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Settings could not be saved."); }
    finally { setBusy(false); }
  }
  async function connectWhatsApp(disconnect = false) {
    setBusy(true); setError("");
    try {
      const response = await apiFetch(`${base}/api/whatsapp/link`, {method: disconnect ? "DELETE" : "POST"});
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "WhatsApp could not connect.");
      if (disconnect) { setLink(null); setData(current => current ? {...current, channels: {...current.channels, whatsapp: {...current.channels.whatsapp, connected: false}}} : current); }
      else setLink(result);
    } catch (failure) { setError(failure instanceof Error ? failure.message : "WhatsApp unavailable."); }
    finally { setBusy(false); }
  }
  const prepared = (data?.prepared || []).filter(item => Object.prototype.hasOwnProperty.call(preparedAreas, item.area)).slice(0, 3);
  if (!open) return null;
  return <aside id="saathi-companion" className="saathi-panel" aria-label="Your farm companion">
    <button ref={close} className="saathi-close" aria-label="Close companion" onClick={onClose}><X size={16}/></button>
    <header className="saathi-identity"><CompanionAvatar/><div><h2 key={data?.name}>{data?.name || "Saathi"}</h2><p key={data?.status || "connecting"}><span className={`saathi-status ${data?.status === "watching" ? "active" : ""}`}/>{data ? statusLabels[data.status] || "Connecting" : "Connecting…"}</p></div></header>
    <GuidedTour scope="companion" steps={companionTour}/><div className="saathi-actions"><button onClick={onVoice}><AudioLines size={16}/> Talk</button><button onClick={() => { setDraft(data?.settings || null); setEditing(value => !value); }} disabled={!data}><Settings2 size={16}/> Personalize</button></div>
    {error && <p className="saathi-error" role="alert">{error}</p>}
    {editing && draft && <form className="saathi-settings" onSubmit={event => { event.preventDefault(); void save(draft); }}>
      <label>Name<input maxLength={40} required value={draft.name} onChange={event => setDraft({ ...draft, name: event.target.value })}/></label>
      <label>Check in<select value={draft.frequency_hours} onChange={event => setDraft({ ...draft, frequency_hours: Number(event.target.value) })}><option value={1}>Every hour</option><option value={6}>Every 6 hours</option><option value={12}>Twice a day</option><option value={24}>Once a day</option><option value={168}>Once a week</option></select></label>
      <div className="saathi-quiet"><Moon size={14}/><span>Quiet hours</span><select aria-label="Quiet hours start" value={draft.quiet_start} onChange={event => setDraft({ ...draft, quiet_start: Number(event.target.value) })}>{Array.from({length:24},(_,hour)=><option key={hour} value={hour}>{String(hour).padStart(2,"0")}:00</option>)}</select><span>–</span><select aria-label="Quiet hours end" value={draft.quiet_end} onChange={event => setDraft({ ...draft, quiet_end: Number(event.target.value) })}>{Array.from({length:24},(_,hour)=><option key={hour} value={hour}>{String(hour).padStart(2,"0")}:00</option>)}</select></div><small>{draft.timezone}</small>
      <button className="saathi-save" disabled={busy}>{busy ? <Loader2 size={14} className="spin"/> : <Check size={14}/>} Save preferences</button>
    </form>}
    {prepared.length > 0 && <section className="saathi-review-list" aria-label="Ready to review"><h3><Sparkles size={13} /> Prepared for you</h3>{prepared.map(item => <CompanionProposal key={item.id} item={item} onNavigate={onClose} onReviewed={proposal => setData(current => current ? {...current, prepared: current.prepared?.map(existing => existing.id === proposal.id ? proposal : existing)} : current)} />)}</section>}
    <section><div className="saathi-section-title"><h3>Farm check-ins</h3>{data && <button disabled={busy} onClick={() => void save({ ...data.settings, enabled: !data.settings.enabled })}>{data.settings.enabled ? <><Pause size={12}/> Pause</> : <><Play size={12}/> Enable</>}</button>}</div></section>
    <section><h3>Stay connected</h3><div className="saathi-channel"><MessageCircle size={15}/><span>This workspace</span><small>Connected</small></div><div className="saathi-channel"><MessageCircle size={15}/><span>WhatsApp</span><small key={String(data?.channels.whatsapp.connected)}>{data?.channels.whatsapp.trial_limited ? "Trial" : data?.channels.whatsapp.connected ? data.channels.whatsapp.masked_number || "Linked" : "Not linked"}</small></div>
      {data?.channels.whatsapp.trial_limited ? <p className="saathi-muted">The trial receives messages but cannot send Saathi's replies yet.</p> : data?.channels.whatsapp.connected ? <button className="saathi-channel-action" disabled={busy} onClick={() => void connectWhatsApp(true)}>Disconnect WhatsApp</button> : data?.channels.whatsapp.configured ? <button className="saathi-channel-action" disabled={busy} onClick={() => void connectWhatsApp()}>Connect WhatsApp</button> : <p className="saathi-muted">WhatsApp connection not configured.</p>}
      {link && !data?.channels.whatsapp.connected && <div className="saathi-link"><p>Send this one-time code from your WhatsApp within 10 minutes.</p><code>{link.message}</code><a href={link.url} target="_blank" rel="noopener noreferrer">Open WhatsApp <ChevronRight size={13}/></a></div>}
</section>
    <section className="saathi-recent"><h3>Recent activity</h3>{!data?.activity.length ? <p className="saathi-muted">Your next check-in will appear here.</p> : <div className="saathi-activity">{data.activity.slice(0,6).map(item => <article key={item.id}><small>{new Date(item.created_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Kolkata" })}</small><strong>{item.title || "Farm check-in"}</strong><p>{item.detail || "Review your farm notebook for the latest follow-ups."}</p>{item.href && /^\/workspace(?:\?|$)/.test(item.href) && <a href={item.href}>Open update <ChevronRight size={13}/></a>}</article>)}</div>}</section>
    <section><h3>Outputs</h3><div className="saathi-outputs">{!artifacts.length ? <p className="saathi-muted">Reports and sheets you create will live here.</p> : artifacts.map(file => <button className="saathi-output" key={file.id} onClick={() => void downloadArtifact(file).catch(failure => setError(failure instanceof Error ? failure.message : "Download unavailable."))}><FileText size={16}/><span>{file.title}<small>{file.format.toUpperCase()}</small></span><ChevronRight size={13}/></button>)}</div></section>
  </aside>;
}
