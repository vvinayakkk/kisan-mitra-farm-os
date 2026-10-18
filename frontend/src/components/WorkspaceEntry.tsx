import { useEffect, useState, type ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { workspaceRequest } from "@/lib/farmWorkspaceClient";
import { needsFarmSetup, setupSkipped, type FarmSetupProfile } from "@/lib/farmSetup";

// Render the workspace immediately; resolve onboarding in the background.
export function WorkspaceEntry({children}: {children:ReactNode}) {
  const [destination,setDestination]=useState<"setup"|"workspace">("workspace");
  const [error,setError]=useState("");
  const [revision,setRevision]=useState(0);
  useEffect(()=>{
    if(setupSkipped()){setDestination("workspace");return;}
    let active=true;
    const controller=new AbortController();
    const timeout=setTimeout(()=>controller.abort(),10000);
    setError("");
    void workspaceRequest<{profile:FarmSetupProfile}>("/api/profile","GET",undefined,{signal:controller.signal,fresh:false})
      .then(({profile})=>{if(active&&!controller.signal.aborted) {if(!profile) throw new Error("Your profile is unavailable. Please retry.");setDestination(needsFarmSetup(profile)&&!setupSkipped()?"setup":"workspace");}})
      .catch(e=>{if(active)setError(controller.signal.aborted?"Your farm is taking longer to connect. Please retry.":e.message);})
      .finally(()=>clearTimeout(timeout));
    return ()=>{active=false;clearTimeout(timeout);controller.abort();};
  },[revision]);
  if(destination==="setup")return <Navigate to="/onboarding" replace/>;
  return <>{children}{error && <div role="status" className="fixed bottom-4 right-4 z-50 rounded-xl bg-background p-3 shadow">Profile sync is taking longer than usual. You can keep working. <button onClick={()=>setRevision(r=>r+1)}>Retry sync</button></div>}</>;
}
