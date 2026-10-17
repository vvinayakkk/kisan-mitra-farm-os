import { currentIdentityToken } from "./firebasePhoneAuth";
export type Column = {
  name: string;
  type: string;
  nullable: boolean;
  default: string | null;
  primary_key: boolean;
  editable: boolean;
  generated?: boolean;
  references: string[];
};
export type Resource = {
  name: string;
  label: string;
  group: string;
  writable: boolean;
  deletable: boolean;
  primary_key: string[];
  columns: Column[];
};
export type Row = Record<string, unknown> & { _version: string };
export type Operation = {
  action: "create" | "update" | "delete";
  key?: Record<string, unknown>;
  values?: Record<string, unknown>;
  version?: string;
};
export type Preview = {
  id: string;
  expires_at: string;
  confirmation: string;
  notice: string;
  changes: {
    action: string;
    key: Record<string, unknown>;
    before: Row | null;
    after: Row | null;
  }[];
};
export async function adminRequest<T>(
  path: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const token = await currentIdentityToken();
  if (!token)
    throw new Error("Sign in with an authorized administrator account.");
  const response = await fetch(
    `${import.meta.env.VITE_API_URL || ""}/admin${path}`,
    {
      method: body === undefined ? "GET" : "POST",
      cache: "no-store",
      credentials: "omit",
      signal,
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    },
  );
  const data = await response
    .json()
    .catch(() => ({
      detail: "The administrator service did not respond. Please try again.",
    }));
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "Check the fields and try again.",
    );
  return data;
}
export function rowOperation(
  resource: Resource,
  row: Row,
  action: "update" | "delete",
  values?: Record<string, unknown>,
): Operation {
  return {
    action,
    key: Object.fromEntries(resource.primary_key.map((k) => [k, row[k]])),
    version: row._version,
    ...(values ? { values } : {}),
  };
}
export function fieldValue(column: Column, value: string): unknown {
  if (value === "null") {
    if (!column.nullable) throw new Error(`${column.name} cannot be empty.`);
    return null;
  }
  if (/JSON/i.test(column.type)) return JSON.parse(value);
  if (/BOOL/i.test(column.type)) {
    if (!["true", "false"].includes(value))
      throw new Error(`${column.name} must be true or false.`);
    return value === "true";
  }
  if (/INT|NUMERIC|DECIMAL|FLOAT|DOUBLE|REAL/i.test(column.type)) {
    if (!value.trim() || !Number.isFinite(Number(value)))
      throw new Error(`${column.name} must be a number.`);
    if (/INT/i.test(column.type)) {
      if (!Number.isSafeInteger(Number(value)))
        throw new Error(`${column.name} must be a safe whole number.`);
      return Number(value);
    }
    return value;
  }
  return value;
}
export function csvText(
  rows: Record<string, unknown>[],
  columns: string[],
): string {
  const cell = (v: unknown) => {
    let text =
      typeof v === "object" && v !== null ? JSON.stringify(v) : String(v ?? "");
    if (/^[\s]*[=+@-]/.test(text)) text = "'" + text;
    return '"' + text.replace(/"/g, '""') + '"';
  };
  return [
    columns.map(cell).join(","),
    ...rows.map((row) => columns.map((c) => cell(row[c])).join(",")),
  ].join("\r\n");
}
export function parseCsv(text: string): Record<string, string>[] {
  if (text.length > 500_000) throw new Error("Use a file smaller than 500 KB.");
  const lines: string[][] = [];
  let row: string[] = [],
    cell = "",
    quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch === '"') {
      if (quoted && text[i + 1] === '"') {
        cell += '"';
        i++;
      } else if (quoted || cell === "") quoted = !quoted;
      else throw new Error("Invalid CSV quoting.");
    } else if (ch === "," && !quoted) {
      row.push(cell);
      cell = "";
    } else if ((ch === "\n" || ch === "\r") && !quoted) {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      row.push(cell);
      if (row.some(Boolean)) lines.push(row);
      row = [];
      cell = "";
    } else cell += ch;
  }
  if (quoted) throw new Error("Unclosed CSV quote.");
  row.push(cell);
  if (row.some(Boolean)) lines.push(row);
  const headers =
    lines.shift()?.map((s) => s.replace(/^\uFEFF/, "").trim()) || [];
  if (
    !headers.length ||
    headers.some((s) => !s) ||
    new Set(headers).size !== headers.length
  )
    throw new Error("CSV needs unique, non-empty column headers.");
  if (lines.length < 1 || lines.length > 100)
    throw new Error("Import between 1 and 100 rows per batch.");
  return lines.map((values) => {
    if (values.length !== headers.length)
      throw new Error("Every CSV row must match the headers.");
    return Object.fromEntries(headers.map((h, i) => [h, values[i]]));
  });
}
