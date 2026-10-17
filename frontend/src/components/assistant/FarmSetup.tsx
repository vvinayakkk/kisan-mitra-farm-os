import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Leaf, X } from "lucide-react";
import { workspaceRequest } from "@/lib/farmWorkspaceClient";
import { onWorkspaceCacheInvalidated } from "@/lib/workspaceCacheLifecycle";
import { needsFarmSetup, type FarmSetupProfile, type StarterPlan } from "@/lib/farmSetup";
import "./farm-setup.css";
export { needsFarmSetup } from "@/lib/farmSetup";
export function FarmSetup({onOpenPlans}:{onOpenPlans:()=>void}) {
  const navigate=useNavigate();
  const [profile,setProfile]=useState<FarmSetupProfile|null>(null);
  const [plans,setPlans]=useState<StarterPlan[]>([]);
  const [revision,setRevision]=useState(0),[error,setError]=useState(""),[dismissed,setDismissed]=useState(false);
  useEffect(()=>onWorkspaceCacheInvalidated(()=>setRevision(r=>r+1)),[]);
  useEffect(()=>{let active=true;void Promise.all([workspaceRequest<{profile:FarmSetupProfile}>("/api/profile"),workspaceRequest<{plans:StarterPlan[]}>("/api/onboarding/starter-plans")]).then(([p,s])=>{if(active){setProfile(p.profile);setPlans(s.plans);setError("");}}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[revision]);
  if(dismissed||(!profile&&!error))return null;
  const incomplete=profile&&needsFarmSetup(profile),allSaved=plans.length>0&&plans.every(p=>p.saved);
  return <aside className="farm-setup-ribbon" aria-label="Your shared farm setup"><Leaf size={18} aria-hidden="true"/><span>{error?"Your farm setup could not refresh.":incomplete?"Mitra can help finish your farm setup.":allSaved?"Your farm plans are saved across app and web.":"A little head start, prepared by Mitra."}</span><button onClick={()=>error?setRevision(r=>r+1):allSaved&&!incomplete?onOpenPlans():navigate(incomplete?"/onboarding":"/onboarding?review=1")}>{error?"Retry":incomplete?"Continue with Mitra":allSaved?"View plans":"Review starter plans"}</button><button aria-label="Dismiss setup reminder for now" onClick={()=>setDismissed(true)}><X size={16}/></button></aside>;
}
