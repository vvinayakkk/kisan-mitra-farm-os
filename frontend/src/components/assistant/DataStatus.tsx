import { localPresentation } from "@/lib/localPresentation";
import "./dataStatus.css";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
export interface Provenance {
  origin?: string;
  lane?: string;
  source?: string;
  observed_at?: string;
  fetched_at?: string;
  stale?: boolean;
  unit?: string;
}
const labels: Record<string, string> = {
  synthetic: "Sample", observed: "Observed", reanalysis: "Reanalysis",
  modeled: "Modelled", forecast: "Forecast", scenario: "Scenario",
  user_reported: "Farmer reported", curated: "Reviewed source", derived: "Calculated",
};
export function provenanceLabel(value?: Provenance | null): string {
  if (!value) return "Source not supplied";
  const label = localPresentation && value.origin === "synthetic" ? "Saved data" : labels[value.origin ?? ""] ?? "Source not supplied";
  return `${label}${value.stale ? " · Older data" : ""}`;
}
export function ProvenanceBadge({ value }: { value?: Provenance | null }) {
  if (localPresentation && value?.origin === "synthetic") return null;
  return <span className={`data-provenance ${value?.stale ? "data-stale" : ""}`} title={[value?.source, value?.observed_at && `Dated ${value.observed_at}`, value?.unit].filter(Boolean).join(" · ")}>{provenanceLabel(value)}</span>;
}
interface DataHealth {
  mode?: string;
  schema?: string;
  connectors?: Record<string, unknown>[] | Record<string, unknown>;
}
export function DataStatus() {
  const [status, setStatus] = useState<DataHealth | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    const refresh = async () => {
      try {
        const base = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");
        const response = await apiFetch(base + "/api/data/status", { signal: controller.signal });
        if (!response.ok) throw new Error("Data status unavailable");
        setStatus(await response.json()); setFailed(false);
      } catch { if (!controller.signal.aborted) setFailed(true); }
    };
    void refresh();
    const interval = window.setInterval(refresh, 60000);
    return () => { controller.abort(); window.clearInterval(interval); };
  }, []);
  return <details className="farm-data-status">
    <summary><span className={`data-status-dot ${failed ? "data-status-offline" : ""}`} />{failed ? "Data connection unavailable" : !status ? "Connecting farm data…" : "Data sources"}</summary>
    <div className="data-status-detail">
      <strong>{failed ? "Please retry shortly" : "Source details"}</strong>
      <p>{!localPresentation && status?.mode?.includes("demo") ? "This workspace includes sample profiles, sensor readings and market scenarios. Connected public sources are labelled separately. Sample actions cannot control real equipment." : "Check the source and reporting date for each record."}</p>
      {status?.connectors && <ul>{(Array.isArray(status.connectors) ? status.connectors : Object.entries(status.connectors).map(([name, value]) => ({ name, ...(typeof value === "object" && value ? value : { status: value }) }))).map((item, i) => <li key={i}><span>{String(item.name ?? item.source ?? item.id ?? "Source")}</span><small>{String(item.status ?? item.state ?? "Configured")}</small></li>)}</ul>}
    </div>
  </details>;
}
