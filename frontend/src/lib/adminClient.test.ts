import { describe, it, expect } from "vitest";
import {
  csvText,
  parseCsv,
  fieldValue,
  Column,
  rowOperation,
  Resource,
} from "./adminClient";
const column = (type: string, nullable = false) =>
  ({ name: "value", type, nullable }) as Column;
describe("admin import and export", () => {
  it("parses quoted commas, quotes, and multiline data", () => {
    expect(parseCsv('name,notes\r\n"Ravi, P","one\n""two"""')).toEqual([
      { name: "Ravi, P", notes: 'one\n"two"' },
    ]);
  });
  it("rejects oversized and malformed imports", () => {
    for (const text of [
      "a,a\n1,2",
      "a,b\n1",
      'a\n"unfinished',
      "a\n" + Array(101).fill("x").join("\n"),
    ])
      expect(() => parseCsv(text)).toThrow();
  });
  it("prevents spreadsheet formula execution on export", () => {
    expect(csvText([{ name: '=HYPERLINK("bad")' }], ["name"])).toContain("'=");
  });
  it("keeps JSON and null typed and rejects invalid booleans and numbers", () => {
    expect(fieldValue(column("JSONB"), "[1]")).toEqual([1]);
    expect(fieldValue(column("TEXT", true), "null")).toBeNull();
    expect(() => fieldValue(column("BOOLEAN"), "yes")).toThrow();
    expect(() => fieldValue(column("INTEGER"), "NaN")).toThrow();
    expect(() => fieldValue(column("INTEGER"), "")).toThrow();
  });
  it("carries complete composite keys and optimistic version", () => {
    expect(
      rowOperation(
        { primary_key: ["id", "day"] } as Resource,
        { id: "a", day: "2026-01-01", _version: "v" },
        "delete",
      ),
    ).toEqual({
      action: "delete",
      key: { id: "a", day: "2026-01-01" },
      version: "v",
    });
  });
});
