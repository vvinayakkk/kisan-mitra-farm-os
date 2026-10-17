import { useEffect, useState, type ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { workspaceRequest } from "@/lib/farmWorkspaceClient";
import { needsFarmSetup, setupSkipped, type FarmSetupProfile } from "@/lib/farmSetup";

// Do not mount chat until the signed-in farmer's setup state is known.
export function WorkspaceEntry({children}: {children:ReactNode}) {
  const [destination,setDestination]=useState<"loading"|"setup"|"workspace">("loading");
  const [error,setError]=useState("");
  const [revision,setRevision]=useState(0);
  useEffect(()=>{
    if(setupSkipped()){setDestination("workspace");return;}
    let active=true;
    const controller=new AbortController();
    const timeout=setTimeout(()=>controller.abort(),10000);
    setError("");
    void workspaceRequest<{profile:FarmSetupProfile}>("/api/profile","GET",undefined,{signal:controller.signal,fresh:true})
      .then(({profile})=>{if(active&&!controller.signal.aborted) {if(!profile) throw new Error("Your profile is unavailable. Please retry.");setDestination(needsFarmSetup(profile)&&!setupSkipped()?"setup":"workspace");}})
      .catch(e=>{if(active)setError(controller.signal.aborted?"Your farm is taking longer to connect. Please retry.":e.message);})
      .finally(()=>clearTimeout(timeout));
    return ()=>{active=false;clearTimeout(timeout);controller.abort();};
  },[revision]);
  if(destination==="setup")return <Navigate to="/onboarding" replace/>;
  if(destination==="workspace")return <>{children}</>;
  return <div className="workspace-loading" role="status">{error||"Opening your farm…"}{error&&<button onClick={()=>setRevision(r=>r+1)}>Retry</button>}</div>;
}
