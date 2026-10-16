import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
const capabilities = vi.hoisted(() => ({ adopt: vi.fn().mockResolvedValue(undefined), clear: vi.fn() }));
vi.mock("@/lib/assistantClient", () => ({ adoptAssistantSession: capabilities.adopt, revokeAssistantSession: capabilities.clear }));
vi.mock("@tanstack/react-query", () => ({ useQueryClient: () => ({ cancelQueries: async () => {}, clear: vi.fn() }) }));
vi.mock("next-themes", () => ({ useTheme: () => ({ setTheme: vi.fn() }) }));
import { AuthProvider, useAuth } from "./AuthContext";
beforeEach(() => {
  const values = new Map<string, string>();
  vi.stubGlobal("localStorage", { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value), removeItem: (key: string) => values.delete(key) });
});
afterEach(() => { vi.unstubAllGlobals(); vi.clearAllMocks(); });
const hook = () => renderHook(() => useAuth(), { wrapper: AuthProvider });
describe("identity verification", () => {
  it("does not let a universal demo OTP authenticate arbitrary phones", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ detail: "Not verified" }, { status: 401 })));
    const { result } = hook(); let ok = true;
    await act(async () => { ok = await result.current.login("9123456789", "999999"); });
    expect(ok).toBe(false); expect(result.current.isAuthenticated).toBe(false); expect(capabilities.adopt).not.toHaveBeenCalled();
  });
  it("does not fall back to browser-stored OTP when offline", async () => {
    localStorage.setItem("saved_user_otp_9123456789", "123456");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Offline"))); const { result } = hook();
    await act(async () => { expect(await result.current.login("9123456789", "123456")).toBe(false); });
    expect(result.current.isAuthenticated).toBe(false);
  });
  it("preserves the server's demo disclosure and installs its exact capability", async () => {
    const fetch = vi.fn().mockResolvedValueOnce(Response.json({ status: "success", otp: "999999", sms_sent: false, demo_bypass: true })).mockResolvedValueOnce(Response.json({ status: "success", token: "server-issued", session_id: "a".repeat(32) }));
    vi.stubGlobal("fetch", fetch); const { result } = hook();
    await act(async () => {
      const issued = await result.current.sendOtp("9999999999"); expect(issued.sms_sent).toBe(false);
      expect(await result.current.login("9999999999", "999999")).toBe(true);
    });
    expect(capabilities.adopt).toHaveBeenCalledWith("a".repeat(32), "server-issued"); expect(result.current.isAuthenticated).toBe(true);
  });
  it("clears workspace capabilities on logout", async () => {
    const { result } = hook(); await act(async () => result.current.logout()); expect(capabilities.clear).toHaveBeenCalled();
  });
});
