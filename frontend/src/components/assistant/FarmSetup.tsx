import { useLocalDraft } from "@/hooks/useLocalDraft";
import { useEffect, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Leaf, X } from "lucide-react";
import { workspaceRequest } from "@/lib/farmWorkspaceClient";
import { onWorkspaceCacheInvalidated } from "@/lib/workspaceCacheLifecycle";
import { WorkspaceVoiceField } from "@/components/WorkspaceVoiceField";
import { APP_LANGUAGES, applyLanguagePreference } from "@/lib/languagePreference";
import "./farm-setup.css";

type Profile = { id: string; name: string; state?: string; region_id?: string; onboarding_required?: boolean; preferred_language?: string; land_size_acres?: number; crops?: string[] };
type Plan = { key: string; title: string; steps: string[]; saved: boolean };
type Options = { regions: {id: string; name: string}[] };
export const needsFarmSetup = (p: Profile) => !!p.onboarding_required || !p.name?.trim() || !p.state || !p.crops?.length || p.land_size_acres == null;

export function FarmSetup({ onOpenPlans }: { onOpenPlans: () => void }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [draft, setDraft, clearDraft] = useLocalDraft("farm-setup");
  const [plans, setPlans] = useState<Plan[]>([]);
  const [options, setOptions] = useState<Options>({regions: []});
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [form, setForm] = useState({name: "", region: "", language: "en", crops: "", area: "", consent: false});
  useEffect(() => onWorkspaceCacheInvalidated(() => setRevision(r => r + 1)), []);
  useEffect(() => {
    let active = true;
    void Promise.all([
      workspaceRequest<{profile: Profile}>("/api/profile"),
      workspaceRequest<{plans: Plan[]}>("/api/onboarding/starter-plans"),
    ]).then(([p, routines]) => {
      if (!active) return;
      setProfile(p.profile); setPlans(routines.plans); setError("");
    }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [revision]);
  const incomplete = profile ? needsFarmSetup(profile) : false;
  useEffect(() => {
    if (open && incomplete) setDraft(JSON.stringify({...form, consent: false}));
  }, [form, open, incomplete, setDraft]);
  const allSaved = plans.length > 0 && plans.every(p => p.saved);
  async function begin() {
    if (!profile) return;
    const initial = {name: profile.name || "", region: profile.region_id || "", language: profile.preferred_language?.split("-")[0] || "en", crops: (profile.crops || []).join(", "), area: profile.land_size_acres?.toString() || "", consent: false};
    try {
      const local = JSON.parse(draft || "null");
      if (local && incomplete) for (const key of ["name", "region", "language", "crops", "area"] as const) {
        if (typeof local[key] === "string") initial[key] = local[key];
      }
    } catch { /* A damaged local draft must not hide saved database details. */ }
    setForm(initial);
    setOpen(true); setError("");
    if (incomplete) {
      try {
        const choices = await workspaceRequest<Options>("/api/onboarding/options");
        setOptions(choices);
        setForm(f => ({...f, region: f.region || choices.regions.find(r => r.name === profile.state)?.id || ""}));
      } catch (e) { setError((e as Error).message); }
    }
  }
  async function saveProfile(event: React.FormEvent) {
    event.preventDefault();
    if (!profile || !form.consent) return;
    setBusy(true); setError("");
    try {
      await workspaceRequest("/api/onboarding", "POST", {display_name: form.name.trim(), region_id: form.region, preferred_language: form.language, consent_to_store_profile: true});
      await workspaceRequest("/api/profile/save", "POST", {name: form.name.trim(), crops: form.crops.split(",").map(c => c.trim()).filter(Boolean), land_size_acres: Number(form.area), preferred_language: form.language});
      const latest = await workspaceRequest<{profile: Profile}>("/api/profile", "GET", undefined, {fresh: true});
      clearDraft(); setProfile(latest.profile); applyLanguagePreference(form.language); setRevision(r => r + 1);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function savePlans() {
    setBusy(true); setError("");
    try {
      await workspaceRequest("/api/onboarding/starter-plans", "POST", {approved: true});
      setPlans(p => p.map(item => ({...item, saved: true}))); setSaved(true);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  if (dismissed && !open) return null;
  if (!profile && !error) return null;
  return <>
    <aside className="farm-setup-ribbon" aria-label="Your shared farm setup">
      <Leaf size={18} aria-hidden="true" />
      <span>{error && !open ? "Your farm setup could not refresh." : incomplete ? "Make yourself at home. Continue your farm setup." : allSaved ? "Your farm plans are saved across app and web." : "A little head start, prepared by Mitra."}</span>
      {error && !open ? <button onClick={() => setRevision(r => r + 1)}>Retry</button> : <button onClick={allSaved && !incomplete ? onOpenPlans : () => void begin()}>{incomplete ? "Continue setup" : allSaved ? "View plans" : "Review starter plans"}</button>}
      <button aria-label="Dismiss setup reminder for now" onClick={() => setDismissed(true)}><X size={16}/></button>
    </aside>
    <Dialog.Root open={open} onOpenChange={next => { if (!busy) setOpen(next); }}>
      <Dialog.Portal><Dialog.Overlay className="farm-setup-overlay"/><Dialog.Content className="farm-setup-dialog" onPointerDownOutside={e => e.preventDefault()}>
        <Dialog.Title>{incomplete ? "Your farm, on every screen." : "A good place to begin."}</Dialog.Title>
        <Dialog.Description>Saved details and plans belong to your account. Use the same phone sign-in in the app or on your laptop.</Dialog.Description>
        <Dialog.Close className="farm-setup-close" aria-label="Close setup" disabled={busy}><X size={20}/></Dialog.Close>
        {error && <p role="alert">{error}</p>}
        {incomplete ? <form onSubmit={saveProfile}>
          <label>Your name<WorkspaceVoiceField onTranscript={name => setForm(f => ({...f, name}))}><input required minLength={2} maxLength={100} value={form.name} onChange={e => setForm({...form, name:e.target.value})}/></WorkspaceVoiceField></label>
          <label>State or union territory<select required value={form.region} onChange={e => setForm({...form, region:e.target.value})}><option value="">Choose your state</option>{options.regions.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}</select></label>
          <label>Language<select value={form.language} onChange={e => setForm({...form, language:e.target.value})}>{APP_LANGUAGES.map(([code,label]) => <option key={code} value={code}>{label}</option>)}</select></label>
          <label>Crops you grow<WorkspaceVoiceField onTranscript={crops => setForm(f => ({...f,crops}))}><input required maxLength={500} value={form.crops} onChange={e => setForm({...form,crops:e.target.value})} placeholder="For example, groundnut, maize"/></WorkspaceVoiceField></label>
          <label>Total land area in acres<input required type="number" min="0.0001" max="100000" step="any" value={form.area} onChange={e => setForm({...form,area:e.target.value})}/></label>
          <label className="farm-setup-consent"><input required type="checkbox" checked={form.consent} onChange={e => setForm({...form,consent:e.target.checked})}/>Save these details to my farm account.</label>
          <p>Unfinished edits stay in this browser until you save. Your saved fields stay unchanged. Add field boundaries and crop seasons in your notebook when you are ready.</p>
          <footer><Dialog.Close disabled={busy}>Skip for now</Dialog.Close><button disabled={busy || !options.regions.length}>{busy ? "Saving…" : "Save and review plans"}</button></footer>
        </form> : <>
          <p>These are editable draft routines, not scheduled tasks or confirmed farm instructions.</p>
          <div className="farm-setup-plans">{plans.map(plan => <article key={plan.key}><h3>{plan.title}{plan.saved ? " · Saved" : ""}</h3><ul>{plan.steps.map(step => <li key={step}>{step}</li>)}</ul></article>)}</div>
          {saved && <p role="status">Saved to your notebook. You can review and customize them on either device.</p>}
          <footer><Dialog.Close disabled={busy}>Skip for now</Dialog.Close>{allSaved ? <button onClick={() => {setOpen(false); onOpenPlans();}}>Open my plans</button> : <button disabled={busy || !plans.length} onClick={() => void savePlans()}>{busy ? "Saving…" : "Save reviewed starter plans"}</button>}</footer>
        </>}
      </Dialog.Content></Dialog.Portal>
    </Dialog.Root>
  </>;
}
