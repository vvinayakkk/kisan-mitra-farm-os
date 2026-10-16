import { Download, FileJson, Sheet } from "lucide-react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { exportCsv, exportJson, type ExportOptions } from "@/lib/farmExports";
import "./farm-exports.css";
export function ExportMenu({
  filename,
  rows,
  columns,
  provenance,
  note,
  disabled = false,
}: ExportOptions & {
  filename: string;
  rows: readonly object[];
  disabled?: boolean;
}) {
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger
        disabled={disabled || !rows.length}
        className="farm-export-trigger"
        aria-label={`Export ${filename.replace(/-/g, " ")}`}
      >
        <Download size={15} />
        <span>Export</span>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          className="farm-export-menu"
          sideOffset={7}
          align="end"
        >
          <DropdownMenu.Label className="farm-export-label">
            Download {rows.length.toLocaleString("en-IN")} loaded{" "}
            {rows.length === 1 ? "record" : "records"}
          </DropdownMenu.Label>
          <DropdownMenu.Item
            onSelect={() =>
              exportCsv(filename, rows, { columns, provenance, note })
            }
          >
            <Sheet size={15} />
            Spreadsheet (CSV)
          </DropdownMenu.Item>
          <DropdownMenu.Item
            onSelect={() =>
              exportJson(filename, { records: rows, provenance, note })
            }
          >
            <FileJson size={15} />
            Full records (JSON)
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
