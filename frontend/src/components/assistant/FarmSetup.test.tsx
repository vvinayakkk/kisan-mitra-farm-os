import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { MemoryRouter, useLocation } from "react-router-dom";
import { FarmSetup } from "./FarmSetup";
const request=vi.hoisted(()=>vi.fn());
vi.mock("@/lib/farmWorkspaceClient",()=>({workspaceRequest:request}));
afterEach(()=>{cleanup();request.mockReset();});
function Location(){return <span data-testid="route">{useLocation().pathname+useLocation().search}</span>;}
function mount(incomplete=false,saved=false){request.mockImplementation(async path=>path==="/api/profile"?{profile:{id:"a",name:"Asha",state:"Maharashtra",crops:["Groundnut"],land_size_acres:4,onboarding_required:incomplete}}:{plans:[{key:"walk",saved}]});const open=vi.fn();render(<MemoryRouter><FarmSetup onOpenPlans={open}/><Location/></MemoryRouter>);return open;}
it("opens full-screen setup instead of a form modal",async()=>{mount(true);fireEvent.click(await screen.findByRole("button",{name:"Continue with Mitra"}));expect(screen.getByTestId("route")).toHaveTextContent("/onboarding");expect(screen.queryByRole("dialog")).not.toBeInTheDocument();});
it("opens starter review without overwriting an app-completed profile",async()=>{mount();fireEvent.click(await screen.findByRole("button",{name:"Review starter plans"}));expect(screen.getByTestId("route")).toHaveTextContent("/onboarding?review=1");expect(request.mock.calls.some(([,method])=>method==="POST")).toBe(false);});
it("opens plans already saved on another device",async()=>{const open=mount(false,true);fireEvent.click(await screen.findByRole("button",{name:"View plans"}));expect(open).toHaveBeenCalledOnce();});
