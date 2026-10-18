import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { WorkspaceEntry } from "./WorkspaceEntry";
const mocks=vi.hoisted(()=>({request:vi.fn(),skipped:false}));
vi.mock("@/lib/farmWorkspaceClient",()=>({workspaceRequest:mocks.request}));
vi.mock("@/lib/assistantClient",()=>({getAssistantSessionId:()=>"test"}));
function mount(){render(<MemoryRouter initialEntries={["/workspace"]}><Routes><Route path="/workspace" element={<WorkspaceEntry><div>Chat content</div></WorkspaceEntry>}/><Route path="/onboarding" element={<div>Guided onboarding</div>}/></Routes></MemoryRouter>);}
afterEach(()=>{cleanup();sessionStorage.clear();mocks.request.mockReset();});
it("shows the workspace immediately while checking onboarding in the background",async()=>{let finish:any;mocks.request.mockReturnValue(new Promise(r=>finish=r));mount();expect(screen.queryByText("Chat content")).toBeInTheDocument();finish({profile:{id:"a",name:"Asha",onboarding_required:true}});expect(await screen.findByText("Guided onboarding")).toBeInTheDocument();expect(screen.queryByText("Chat content")).not.toBeInTheDocument();});
it("takes returning app-completed users straight to the workspace",async()=>{mocks.request.mockResolvedValue({profile:{id:"a",name:"Asha",state:"Maharashtra",crops:["Maize"],land_size_acres:4}});mount();expect(await screen.findByText("Chat content")).toBeInTheDocument();});
it("honours an explicit skip for this signed-in session",async()=>{sessionStorage.setItem("mitra-setup-skipped:test","true");mount();expect(await screen.findByText("Chat content")).toBeInTheDocument();expect(mocks.request).not.toHaveBeenCalled();});
it("keeps the workspace usable when profile sync fails",async()=>{mocks.request.mockRejectedValue(new Error("Offline"));mount();expect(await screen.findByRole("button",{name:"Retry sync"})).toBeInTheDocument();expect(screen.queryByText("Chat content")).toBeInTheDocument();});
