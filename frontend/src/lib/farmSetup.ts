import { getAssistantSessionId } from "./assistantClient";
export type FarmSetupProfile = {id:string;name:string;state?:string;region_id?:string;onboarding_required?:boolean;preferred_language?:string;land_size_acres?:number;crops?:string[]};
export type StarterPlan = {key:string;title:string;steps:string[];saved:boolean};
export const needsFarmSetup = (p: FarmSetupProfile) => !!p.onboarding_required || !p.name?.trim() || !p.state || !p.crops?.length || p.land_size_acres == null;
const skipKey = () => `mitra-setup-skipped:${getAssistantSessionId() || "pending"}`;
export function setupSkipped() { try { return sessionStorage.getItem(skipKey()) === "true"; } catch { return false; } }
export function skipSetup() { try { sessionStorage.setItem(skipKey(), "true"); } catch { /* Navigation still works without browser storage. */ } }
