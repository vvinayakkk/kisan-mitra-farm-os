import { expect, it, vi, afterEach } from "vitest";
import { buildCsv, csvCell, downloadText } from "./farmExports";
afterEach(() => vi.restoreAllMocks());
it("keeps malicious spreadsheet formulas as literal text including whitespace prefixes", () => {
  for (const value of [
    '=HYPERLINK("https://evil.example")',
    " +SUM(1,2)",
    "\t@command",
    "-danger",
  ])
    expect(csvCell(value)).toMatch(/^"'/);
  expect(csvCell(-12.5)).toBe('"-12.5"');
  expect(csvCell('Seeds, "fresh"\npaid')).toBe('"Seeds, ""fresh""\npaid"');
});
it("preserves units, provenance and records rather than generating missing amounts", () => {
  const csv = buildCsv(
    [
      { description: "Seeds", amount_inr: 1250, basis: "actual" },
      { description: "Sale", amount_inr: null, basis: "estimated" },
    ],
    {
      columns: [
        { key: "description", label: "Description" },
        { key: "amount_inr", label: "Amount (INR)" },
        { key: "basis", label: "Basis" },
      ],
      provenance: { origin: "synthetic" },
      note: "Actual is separate from estimated.",
    },
  );
  expect(csv).toContain('"Amount (INR)"');
  expect(csv).toContain('"Seeds","1250","actual"');
  expect(csv).toContain('"Sale","","estimated"');
  expect(csv).toContain("synthetic");
  expect(csv.startsWith("\ufeff")).toBe(true);
});
it("handles heterogeneous rows and exports nested records as escaped JSON", () => {
  const csv = buildCsv([
    { name: "Field A" },
    { area_ha: 1.5, notes: { state: "growing" } },
  ]);
  expect(csv).toContain('"name","area ha","notes"');
  expect(csv).toContain('"","1.5","{""state"":""growing""}"');
});
it("downloads locally and revokes the temporary blob URL", () => {
  vi.useFakeTimers();
  const create = vi.fn(() => "blob:local"),
    revoke = vi.fn();
  vi.stubGlobal("URL", { createObjectURL: create, revokeObjectURL: revoke });
  const click = vi
    .spyOn(HTMLAnchorElement.prototype, "click")
    .mockImplementation(() => {});
  downloadText("my/profile.txt", "private");
  expect(click).toHaveBeenCalledOnce();
  expect(document.querySelector("a")).toBeNull();
  expect(create).toHaveBeenCalledOnce();
  vi.runAllTimers();
  expect(revoke).toHaveBeenCalledWith("blob:local");
  vi.unstubAllGlobals();
  vi.useRealTimers();
});
