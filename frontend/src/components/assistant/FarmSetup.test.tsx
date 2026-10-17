import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { FarmSetup } from "./FarmSetup";
const request = vi.hoisted(() => vi.fn());
vi.mock("@/hooks/useLocalDraft", () => ({useLocalDraft: () => ["", vi.fn(), vi.fn()]}));
vi.mock("@/lib/farmWorkspaceClient", () => ({workspaceRequest: request}));
vi.mock("@/components/WorkspaceVoiceField", () => ({WorkspaceVoiceField: ({children}: any) => children}));
vi.mock("@/lib/languagePreference", () => ({APP_LANGUAGES:[["en","English"]], applyLanguagePreference:vi.fn()}));
const existing = {id:"farmer",name:"Asha",state:"Maharashtra",region_id:"region",crops:["Groundnut"],land_size_acres:3,preferred_language:"en",onboarding_required:false};
let profile = {...existing};
let saved = false;
beforeEach(() => {
  saved = false; profile = {...existing}; request.mockReset();
  request.mockImplementation(async (path, method, body) => {
    if (path === "/api/profile") return {profile};
    if (path === "/api/onboarding/options") return {regions:[{id:"region",name:"Maharashtra"}]};
    if (path === "/api/onboarding") {profile={...profile,name:body.display_name,state:"Maharashtra",onboarding_required:false}; return {saved:true};}
    if (path === "/api/profile/save") {profile={...profile,...body}; return {profile};}
    if (path === "/api/onboarding/starter-plans" && method === "POST") {saved=true; return {saved:true};}
    if (path === "/api/onboarding/starter-plans") return {plans:[{key:"morning-walk",title:"My morning farm walk",steps:["Check the local forecast"],saved}]};
    throw new Error("Unexpected request " + path);
  });
});
afterEach(cleanup);
it("uses an app-completed profile without writing over it and saves plans only after review", async () => {
  const openPlans=vi.fn(); render(<FarmSetup onOpenPlans={openPlans}/>);
  fireEvent.click(await screen.findByRole("button",{name:"Review starter plans"}));
  expect(await screen.findByText("My morning farm walk")).toBeInTheDocument();
  expect(screen.queryByLabelText("Your name")).not.toBeInTheDocument();
  expect(request.mock.calls.some(([,method])=>method === "POST")).toBe(false);
  fireEvent.click(screen.getByRole("button",{name:"Save reviewed starter plans"}));
  await screen.findByRole("button",{name:"Open my plans"});
  expect(request).toHaveBeenCalledWith("/api/onboarding/starter-plans","POST",{approved:true});
  fireEvent.click(screen.getByRole("button",{name:"Open my plans"}));
  expect(openPlans).toHaveBeenCalledOnce();
});
it("recognizes starter plans already saved on another device", async () => {
  saved=true; render(<FarmSetup onOpenPlans={vi.fn()}/>);
  await screen.findByRole("button",{name:"View plans"});
  expect(request.mock.calls.some(([,method])=>method === "POST")).toBe(false);
});
it("prefills a partial database profile and saves setup before offering plans", async () => {
  profile={...existing,crops:[],land_size_acres:null as any,onboarding_required:true};
  render(<FarmSetup onOpenPlans={vi.fn()}/>);
  fireEvent.click(await screen.findByRole("button",{name:"Continue setup"}));
  expect(await screen.findByLabelText("Your name")).toHaveValue("Asha");
  fireEvent.change(screen.getByLabelText("Crops you grow"),{target:{value:"Groundnut"}});
  fireEvent.change(screen.getByLabelText("Total land area in acres"),{target:{value:"4"}});
  fireEvent.click(screen.getByRole("checkbox"));
  await waitFor(()=>expect(screen.getByRole("button",{name:"Save and review plans"})).not.toBeDisabled());
  fireEvent.click(screen.getByRole("button",{name:"Save and review plans"}));
  await screen.findByRole("button",{name:"Save reviewed starter plans"});
  expect(request).toHaveBeenCalledWith("/api/profile/save","POST",expect.objectContaining({land_size_acres:4,crops:["Groundnut"]}));
});
it("reports failure and does not pretend plans were saved", async () => {
  const original=request.getMockImplementation()!;
  request.mockImplementation((path,method,...args)=>method === "POST" ? Promise.reject(new Error("Connection interrupted")) : original(path,method,...args));
  render(<FarmSetup onOpenPlans={vi.fn()}/>);
  fireEvent.click(await screen.findByRole("button",{name:"Review starter plans"}));
  fireEvent.click(await screen.findByRole("button",{name:"Save reviewed starter plans"}));
  expect(await screen.findByRole("alert")).toHaveTextContent("Connection interrupted");
  expect(screen.getByRole("button",{name:"Save reviewed starter plans"})).not.toBeDisabled();
});
