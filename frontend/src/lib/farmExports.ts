export type ExportRow = Record<string, unknown>;
export type ExportColumn = { key: string; label: string };
export type ExportOptions = {
  columns?: ExportColumn[];
  provenance?: unknown;
  note?: string;
};
export function csvCell(value: unknown): string {
  let text =
    value == null
      ? ""
      : typeof value === "object"
        ? JSON.stringify(value)
        : String(value);

  if (
    /^[\s\u0000-\u001f]*[=+\-@]/.test(text) &&
    !(typeof value === "number" && Number.isFinite(value))
  )
    text = `'${text}`;
  return `"${text.replace(/"/g, '""')}"`;
}
export function buildCsv(
  rows: readonly object[],
  options: ExportOptions = {},
): string {
  const columns =
    options.columns ||
    Array.from(new Set(rows.flatMap((row) => Object.keys(row)))).map((key) => ({
      key,
      label: key.replace(/_/g, " "),
    }));
  const metadata = [
    ["Exported at (UTC)", new Date().toISOString()],
    ...(options.provenance
      ? [["Data provenance", JSON.stringify(options.provenance)]]
      : []),
    ...(options.note ? [["Notes", options.note]] : []),
  ];
  return (
    "\ufeff" +
    [
      ...metadata.map((row) => row.map(csvCell).join(",")),
      "",
      columns.map((column) => csvCell(column.label)).join(","),
      ...rows.map((row) =>
        columns
          .map((column) => csvCell((row as ExportRow)[column.key]))
          .join(","),
      ),
    ].join("\r\n")
  );
}
export function downloadText(
  filename: string,
  text: string,
  mime = "text/plain;charset=utf-8",
) {
  const url = URL.createObjectURL(new Blob([text], { type: mime }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename.replace(/[^a-zA-Z0-9._-]/g, "-");
  document.body.append(link);
  link.click();
  link.remove();

  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function exportCsv(
  filename: string,
  rows: readonly object[],
  options: ExportOptions = {},
) {
  downloadText(
    `${filename.replace(/\.csv$/i, "")}.csv`,
    buildCsv(rows, options),
    "text/csv;charset=utf-8",
  );
}
export function exportJson(filename: string, data: unknown) {
  downloadText(
    `${filename.replace(/\.json$/i, "")}.json`,
    JSON.stringify({ exported_at: new Date().toISOString(), data }, null, 2),
    "application/json;charset=utf-8",
  );
}
