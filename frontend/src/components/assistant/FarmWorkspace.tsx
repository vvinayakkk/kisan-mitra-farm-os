import { CollectionFilters, useCollectionFilters } from "./CollectionFilters";
import { onWorkspaceCacheInvalidated } from "@/lib/workspaceCacheLifecycle";
import { localPresentation } from "@/lib/localPresentation";
import type { ExportColumn } from "@/lib/farmExports";
import { ExportMenu } from "./ExportMenu";
import { FieldMap } from "./FieldMap";
import { SharedFarmWork } from "./SharedFarmWork";
import { sendAssistant, useAssistant } from "@/lib/assistantClient";
import { parseSpokenNumber, parseSpokenDate } from "@/lib/voiceNumbers";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useEffect, useState } from "react";
import {
  ArrowUpRight,
  Loader2,
  Plus,
  X,
  Pencil,
  Trash2,
  Sprout,
} from "lucide-react";
import { workspaceRequest } from "@/lib/farmWorkspaceClient";
export { workspaceRequest } from "@/lib/farmWorkspaceClient";
import { WorkspaceVoiceField } from "@/components/WorkspaceVoiceField";
import { ProvenanceBadge, type Provenance } from "./DataStatus";
import "./farm-workspace.css";
function displayDate(value: unknown) {
  if (typeof value !== "string") return "";
  const date = new Date(
    value.length === 10 ? `${value}T00:00:00+05:30` : value,
  );
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
        timeZone: "Asia/Kolkata",
        ...(value.includes("T") ? { hour: "numeric", minute: "2-digit" } : {}),
      }).format(date);
}
function friendlyDetail(value: unknown) {
  return typeof value === "string"
    ? value.replace(
        /\d{4}-\d{2}-\d{2}T[\d:.]+(?:Z|[+-]\d{2}:?\d{2})?/g,
        (match) => displayDate(match),
      )
    : "";
}
type Row = Record<string, any>;
const recordExportColumns: Record<string, ExportColumn[]> = {
  ledger: [
    ["occurred_on", "Date"],
    ["description", "Description"],
    ["amount_inr", "Amount (INR)"],
    ["kind", "Income or expense"],
    ["basis", "Actual / estimated / receivable"],
    ["category", "Category"],
    ["notes", "Notes"],
    ["origin", "Data origin"],
  ].map(([key, label]) => ({ key, label })),
  cases: [
    ["title", "Crop follow-up"],
    ["status", "Status"],
    ["assessment", "Recorded assessment (not confirmed diagnosis)"],
    ["created_at", "Created at"],
    ["updated_at", "Updated at"],
    ["note_count", "Saved notes"],
  ].map(([key, label]) => ({ key, label })),
  missions: [
    ["title", "Plan"],
    ["objective", "Goal"],
    ["status", "Status"],
    ["steps", "Steps"],
    ["created_at", "Created at"],
    ["updated_at", "Updated at"],
  ].map(([key, label]) => ({ key, label })),
  memories: [
    ["fact_key", "Fact"],
    ["value", "Saved value"],
    ["confidence", "Confidence"],
    ["valid_from", "Saved at"],
  ].map(([key, label]) => ({ key, label })),
};
function useRows(path: string, key: string) {
  const [items, setItems] = useState<Row[]>([]),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0),
    [summary, setSummary] = useState<Row | null>(null);
  useEffect(() => onWorkspaceCacheInvalidated(() => setRevision(value => value + 1)), []);
  useEffect(() => {
    const abort = new AbortController();
    setLoading(true);
    setError("");
    void workspaceRequest<Row>(path, "GET", undefined, {signal: abort.signal, fresh: revision > 0})
      .then((data) => {
        if (!abort.signal.aborted) {
          setItems(data[key] || data.items || []);
          setSummary(data.summary || null);
        }
      })
      .catch((e) => {
        if (!abort.signal.aborted) setError(e.message);
      })
      .finally(() => {
        if (!abort.signal.aborted) setLoading(false);
      });
    return () => abort.abort();
  }, [path, key, revision]);
  return {
    items,
    summary,
    error,
    loading,
    refresh: () => setRevision((n) => n + 1),
  };
}
function Failure({ error }: { error: string }) {
  return error ? (
    <p className="workspace-error" role="alert">
      {error}
    </p>
  ) : null;
}
function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="farm-quiet-empty">
      <Sprout size={24} />
      <p>{children}</p>
    </div>
  );
}
function Field({
  label,
  value,
  onChange,
  type = "text",
  required = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  required?: boolean;
}) {
  const [voiceError, setVoiceError] = useState("");
  function acceptTranscript(text: string) {
    try {
      let result = text;
      if (type === "number") {
        const isLatitude = label.toLowerCase().includes("latitude"),
          isLongitude = label.toLowerCase().includes("longitude");
        result = String(
          parseSpokenNumber(text, {
            unit: label.toLowerCase().includes("rupee")
              ? "rupees"
              : label.toLowerCase().includes("hectare")
                ? "hectares"
                : "number",
            min: isLatitude ? -90 : isLongitude ? -180 : 0,
            max: isLatitude ? 90 : isLongitude ? 180 : undefined,
          }),
        );
      } else if (type === "date") result = parseSpokenDate(text);
      onChange(result);
      setVoiceError("");
    } catch (error) {
      setVoiceError((error as Error).message);
    }
  }
  return (
    <label className="farm-form-field">
      {label}
      <WorkspaceVoiceField
        label={`Speak ${label.toLowerCase()}`}
        onTranscript={acceptTranscript}
      >
        <input
          aria-label={label}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          type={type}
          required={required}
          step={type === "number" ? "any" : undefined}
        />
      </WorkspaceVoiceField>
      {voiceError && (
        <span role="alert" className="farm-voice-error">
          {voiceError}
        </span>
      )}
    </label>
  );
}
function Editor({
  title,
  children,
  onClose,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
}) {
  return (
    <DialogPrimitive.Root
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="farm-editor-overlay" />
        <DialogPrimitive.Content
          className="farm-editor farm-editor-modal"
          aria-describedby={undefined}
        >
          <header>
            <DialogPrimitive.Title asChild>
              <h2>{title}</h2>
            </DialogPrimitive.Title>
            <button type="button" aria-label="Close editor" onClick={onClose}>
              <X size={18} />
            </button>
          </header>
          {children}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

export function Today({ onNavigate }: { onNavigate: (view: string) => void }) {
  const [data, setData] = useState<Row | null>(null),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    void workspaceRequest<Row>("/api/farm-workspace/today")
      .then((d) => {
        if (active) setData(d);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, []);
  return (
    <section className="farm-today">
      <div className="farm-section-heading">
        <div>
          <h2>Your day at a glance</h2>
        </div>
        <time>
          {new Intl.DateTimeFormat("en-IN", {
            day: "numeric",
            month: "long",
            timeZone: "Asia/Kolkata",
          }).format(new Date())}
        </time>
      </div>
      <Failure error={error} />
      {!data && !error && (
        <p>
          <Loader2 className="spin" size={16} /> Gathering your saved farm
          activity…
        </p>
      )}
      {data && (
        <>
          <ProvenanceBadge value={data.provenance as Provenance} />
          <div className="farm-today-actions">
            {(data.actions || []).slice(0, 3).map((a: Row) => (
              <button
                key={a.id}
                onClick={() => {
                  if (a.kind === "crop_case") {
                    onNavigate("notebook-cases");
                    return;
                  }
                  const href = a.href || "";
                  const view = new URL(
                    href,
                    window.location.origin,
                  ).searchParams.get("view");
                  onNavigate(
                    [
                      "chat",
                      "calendar",
                      "records",
                      "crops",
                      "markets",
                      "station",
                      "schemes",
                    ].includes(href)
                      ? href
                      : view ||
                          (a.kind === "task"
                            ? "calendar"
                            : a.kind === "case"
                              ? "crops"
                              : "chat"),
                  );
                }}
              >
                <span className="farm-action-kind">
                  {a.kind?.replace(/_/g, " ") || "Next step"}
                </span>
                <strong>{a.title}</strong>
                <span>{friendlyDetail(a.detail)}</span>
                <ArrowUpRight size={18} />
              </button>
            ))}
          </div>
          {!data.actions?.length && (
            <Empty>
              No urgent saved work. Add your field or plan your next farm task
              with Mitra.
            </Empty>
          )}
          <WeatherContext />
          <div className="farm-day-summary">
            <span>{data.counts?.tasks || 0} open tasks</span>
            <span>{data.counts?.cases || 0} crop follow-ups</span>
            <span>{data.counts?.missions || 0} ongoing plans</span>
          </div>
          <p className="feature-footnote">
            Based on your saved tasks and crop follow-ups.
          </p>
        </>
      )}
    </section>
  );
}
function Fields() {
  const farms = useRows("/api/farms", "farms"),
    plots = useRows("/api/plots", "plots");
  const [regions, setRegions] = useState<Row[]>([]),
    [edit, setEdit] = useState<Row | null>(null),
    [kind, setKind] = useState<"farm" | "plot">("farm"),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    void workspaceRequest<Row>("/api/onboarding/options")
      .then((d) => setRegions(d.regions || []))
      .catch((e) => setError(e.message));
  }, []);
  const farmFilter = useCollectionFilters(farms.items, f => `${f.name || ""} ${f.irrigation_method || ""}`, f => String(f.ownership_type || ""));
  const open = (type: "farm" | "plot", row?: Row) => {
    setKind(type);
    setError("");
    setEdit(
      row ||
        (type === "farm"
          ? {
              name: "",
              region_id: regions[0]?.id || "",
              ownership_type: "owned",
              irrigation_method: "rainfed",
              water_source: "",
            }
          : {
              farm_id: farms.items[0]?.id || "",
              area_ha: "",
              latitude: "",
              longitude: "",
              soil_texture: "",
            }),
    );
  };
  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!edit) return;
    setBusy(true);
    setError("");
    try {
      const payload =
        kind === "farm"
          ? {
              name: edit.name,
              region_id: edit.region_id,
              ownership_type: edit.ownership_type,
              irrigation_method: edit.irrigation_method,
              water_source: edit.water_source || null,
            }
          : {
              farm_id: edit.farm_id,
              name: edit.name || "",
              area_ha: Number(edit.area_ha),
              latitude: Number(edit.latitude),
              longitude: Number(edit.longitude),
              soil_texture: edit.soil_texture || null,
              boundary_geojson: edit.boundary_geojson || null,
            };
      await workspaceRequest(
        `/api/${kind === "farm" ? "farms" : "plots"}${edit.id ? `/${edit.id}` : ""}`,
        edit.id ? "PUT" : "POST",
        payload,
      );
      setEdit(null);
      farms.refresh();
      plots.refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const change = (key: string, value: string) =>
    setEdit((current) => ({ ...current, [key]: value }));
  return (
    <section>
      <div className="farm-section-heading">
        <div>
          <h2>Your land, in one place.</h2>
          <p>
            Keep each field’s details separate. Coordinates are stored only
            after you save.
          </p>
        </div>
        <div className="farm-section-actions">
          <ExportMenu
            filename="my-fields"
            columns={[
              { key: "name", label: "Field name" },
              { key: "farm_name", label: "Farm" },
              { key: "area_ha", label: "Area (hectares)" },
              { key: "soil_texture", label: "Soil texture" },
              { key: "latitude", label: "Latitude" },
              { key: "longitude", label: "Longitude" },
              { key: "boundary_geojson", label: "Recorded boundary" },
            ]}
            rows={plots.items.map((plot) => ({
              ...plot,
              farm_name:
                farms.items.find((farm) => farm.id === plot.farm_id)?.name ||
                "",
            }))}
            disabled={plots.loading || !!plots.error}
            note="Owned saved fields. Areas are hectares; coordinates and boundaries are private. Data origin, when present, identifies sample records."
          />
          <button className="feature-primary" onClick={() => open("farm")}>
            <Plus size={15} /> Add farm
          </button>
        </div>
      </div>
      <CollectionFilters control={farmFilter} label="Farms" />
      <Failure error={farms.error || plots.error || (!edit ? error : "")} />
      {farms.loading ? (
        <p>Loading your fields…</p>
      ) : farms.items.length ? (
        farmFilter.items.map((f) => (
          <article className="feature-card farm-field-card" key={f.id}>
            <div className="farm-section-heading">
              <div>
                <h3>{f.name}</h3>
                <span className="feature-source">
                  {f.ownership_type} · {f.irrigation_method} irrigation
                </span>
              </div>
              <button
                aria-label={`Edit ${f.name}`}
                onClick={() => open("farm", f)}
              >
                <Pencil size={16} />
              </button>
            </div>
            {plots.items
              .filter((p) => p.farm_id === f.id)
              .map((p) => (
                <div className="farm-plot-row" key={p.id}>
                  <Sprout size={17} />
                  <span>
                    {p.name && <strong>{p.name}</strong>}
                    <strong>
                      {Number(p.area_ha).toLocaleString("en-IN")} hectares
                    </strong>
                    <small>
                      {p.soil_texture || "Soil texture not recorded"} ·{" "}
                      {p.latitude}, {p.longitude}
                    </small>
                  </span>
                  <button
                    aria-label={`Edit field ${p.name || p.plot_key}`}
                    onClick={() => open("plot", p)}
                  >
                    <Pencil size={15} />
                  </button>
                </div>
              ))}
            <button
              className="farm-text-action"
              onClick={() =>
                open("plot", {
                  farm_id: f.id,
                  area_ha: "",
                  latitude: "",
                  longitude: "",
                  soil_texture: "",
                })
              }
            >
              <Plus size={14} /> Add a field to this farm
            </button>
            <FieldMap
              plots={plots.items.filter((p) => p.farm_id === f.id) as any}
              onEdit={(p) => open("plot", p)}
            />
            <FarmWeather
              farm={f}
              plots={plots.items.filter((p) => p.farm_id === f.id)}
            />
          </article>
        ))
      ) : (
        <Empty>
          Add your first farm, then its fields. Your region and crop context
          help make advice more useful.
        </Empty>
      )}
      {edit && (
        <Editor
          title={`${edit.id ? "Edit" : "Add"} ${kind === "farm" ? "farm" : "field"}`}
          onClose={() => !busy && setEdit(null)}
        >
          <form onSubmit={save}>
            <Failure error={error} />
            {kind === "farm" ? (
              <>
                <Field
                  label="Farm name"
                  required
                  value={edit.name}
                  onChange={(v) => change("name", v)}
                />
                <label className="farm-form-field">
                  State or union territory
                  <select
                    required
                    value={edit.region_id}
                    onChange={(e) => change("region_id", e.target.value)}
                  >
                    {regions.map((r) => (
                      <option value={r.id} key={r.id}>
                        {r.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="farm-form-field">
                  Ownership
                  <select
                    value={edit.ownership_type}
                    onChange={(e) => change("ownership_type", e.target.value)}
                  >
                    {["owned", "leased", "shared"].map((v) => (
                      <option key={v}>{v}</option>
                    ))}
                  </select>
                </label>
                <label className="farm-form-field">
                  Irrigation
                  <select
                    value={edit.irrigation_method}
                    onChange={(e) =>
                      change("irrigation_method", e.target.value)
                    }
                  >
                    {[
                      "rainfed",
                      "drip",
                      "sprinkler",
                      "flood",
                      "manual",
                      "other",
                    ].map((v) => (
                      <option key={v}>{v}</option>
                    ))}
                  </select>
                </label>
                <Field
                  label="Water source"
                  value={edit.water_source || ""}
                  onChange={(v) => change("water_source", v)}
                />
              </>
            ) : (
              <>
                <Field
                  label="Field name"
                  value={edit.name || ""}
                  onChange={(v) => change("name", v)}
                />
                <Field
                  label="Area in hectares"
                  type="number"
                  required
                  value={String(edit.area_ha)}
                  onChange={(v) => change("area_ha", v)}
                />
                <Field
                  label="Latitude"
                  type="number"
                  required
                  value={String(edit.latitude)}
                  onChange={(v) => change("latitude", v)}
                />
                <Field
                  label="Longitude"
                  type="number"
                  required
                  value={String(edit.longitude)}
                  onChange={(v) => change("longitude", v)}
                />
                <Field
                  label="Soil texture"
                  value={edit.soil_texture || ""}
                  onChange={(v) => change("soil_texture", v)}
                />
                <p className="feature-footnote">
                  Use coordinates from your map. This form doesn’t send them to
                  a weather provider.
                </p>
              </>
            )}
            <footer>
              <button
                type="button"
                onClick={() => setEdit(null)}
                disabled={busy}
              >
                Cancel
              </button>
              <button className="feature-primary" disabled={busy}>
                {busy ? "Saving…" : "Save details"}
              </button>
            </footer>
          </form>
        </Editor>
      )}
    </section>
  );
}
export type NotebookTab =
  | "today"
  | "fields"
  | "ledger"
  | "cases"
  | "missions"
  | "memory"
  | "files";
export function FarmWorkspace({
  tab,
  onNavigate,
}: {
  tab: NotebookTab;
  onNavigate: (view: string) => void;
}) {
  if (tab === "today") return <Today onNavigate={onNavigate} />;
  if (tab === "fields")
    return (
      <>
        <Fields />
        <CropSeasons />
        <FarmTimeline />
      </>
    );
  return <WorkflowRecords tab={tab} onNavigate={onNavigate} />;
}
function WorkflowRecords({
  tab,
  onNavigate,
}: {
  tab: NotebookTab;
  onNavigate: (view: string) => void;
}) {
  const assistant = useAssistant();
  const resource = tab === "memory" ? "memories" : tab;
  const rows = useRows(`/api/farm-workspace/${resource}`, "items");
  const [edit, setEdit] = useState<Row | null>(null),
    [visible, setVisible] = useState(5),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [expanded, setExpanded] = useState<string | null>(null),
    [history, setHistory] = useState<Record<string, Row[]>>({});
  const filter = useCollectionFilters(rows.items, r => [r.title,r.name,r.description,r.notes,r.summary,r.value,r.crop_name,r.fact_key,r.fact,r.key].filter(Boolean).map(String).join(" "), r => String(r.status || r.kind || r.entry_type || r.category || ""), r => String(r.occurred_on || r.observed_on || r.created_at || ""));
  const titles: Record<string, string> = {
    ledger: "Money in & money out",
    cases: "Crop follow-ups",
    missions: "Your farm plans",
    memory: "Your farm details",
  };
  useEffect(() => {
    filter.setFilters({query:"",status:"",from:"",to:""});
    setEdit(null);
    setExpanded(null);
    setVisible(5);
    setHistory({});
    setError("");
  }, [tab]);
  async function loadHistory(r: Row) {
    try {
      const data = await workspaceRequest<Row>(
        `/api/farm-workspace/${resource}/${r.id}/${tab === "cases" ? "notes" : "receipts"}`,
      );
      setHistory((current) => ({ ...current, [r.id]: data.items || [] }));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function mutate(method: string, id?: string, body?: Row) {
    setBusy(true);
    setError("");
    try {
      await workspaceRequest(
        `/api/farm-workspace/${resource}${id ? `/${id}` : ""}${method === "DELETE" && tab === "ledger" ? `?row_version=${body?.row_version}` : ""}`,
        method,
        method === "DELETE" ? undefined : body,
      );
      setEdit(null);
      setHistory({});
      rows.refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function saveEdited() {
    if (!edit) return;
    if (edit.add_note) {
      setBusy(true);
      setError("");
      try {
        await workspaceRequest(
          `/api/farm-workspace/cases/${edit.id}/notes`,
          "POST",
          { note: edit.observation, observed_on: edit.observed_on },
        );
        setEdit(null);
        setHistory({});
        rows.refresh();
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setBusy(false);
      }
      return;
    }
    let body: Row;
    if (tab === "ledger")
      body = {
        description: edit.description,
        category: edit.category,
        kind: edit.kind,
        basis: edit.basis,
        amount_inr: Number(edit.amount_inr),
        occurred_on: edit.occurred_on,
        notes: edit.notes || "",
        cycle_id: edit.cycle_id || null,
        ...(edit.id ? { row_version: edit.row_version } : {}),
      };
    else if (tab === "memory") body = { value: edit.correction };
    else if (tab === "cases")
      body = edit.id
        ? {
            title: edit.title,
            status: edit.status,
            row_version: edit.row_version,
          }
        : {
            title: edit.title,
            note: edit.note || "",
            cycle_id: edit.cycle_id || null,
          };
    else
      body = {
        title: edit.title,
        objective: edit.objective || "",
        steps: (edit.steps || []).filter((step: Row) => step.title.trim()),
        ...(edit.id
          ? { row_version: edit.row_version, status: edit.status }
          : {}),
      };
    await mutate(edit.id ? "PATCH" : "POST", edit.id, body);
  }
  function newRecord() {
    setEdit(
      tab === "ledger"
        ? {
            description: "",
            amount_inr: "",
            kind: "expense",
            basis: "actual",
            category: "other",
            occurred_on: new Intl.DateTimeFormat("en-CA", {
              timeZone: "Asia/Kolkata",
              year: "numeric",
              month: "2-digit",
              day: "2-digit",
            }).format(new Date()),
          }
        : tab === "cases"
          ? { title: "", note: "" }
          : { title: "", objective: "", steps: [], status: "draft" },
    );
  }
  const change = (key: string, value: string) =>
    setEdit((current) => ({ ...current, [key]: value }));
  return (
    <section className="farm-workflow-records">
      <div className="farm-section-heading">
        <div>
          <h2>{titles[tab]}</h2>
          <p>
            {tab === "memory"
              ? "Keep the details Mitra remembers up to date. Correct or forget a note anytime."
              : tab === "missions"
                ? "Choose a plan to check your progress or take the next step."
                : tab === "cases"
                  ? "Add a crop note and keep track of what changes."
                  : "Record a sale or expense. Your balance updates as you go."}
          </p>
        </div>
        <div className="farm-section-actions">
          <ExportMenu
            filename={`my-${resource}`}
            rows={rows.items}
            columns={recordExportColumns[resource]}
            disabled={rows.loading || !!rows.error}
            provenance={
              rows.summary?.includes_demo_fixtures
                ? { origin: "synthetic", lane: "demo" }
                : undefined
            }
            note={
              tab === "ledger"
                ? "Amounts are INR. Actual, estimated and receivable entries remain distinct; export includes all loaded records, not only the first visible rows."
                : "All loaded owned records. Saved plans do not prove completed field work; crop notes do not confirm diagnosis."
            }
          />
          {tab !== "memory" && (
            <button className="feature-primary" onClick={newRecord}>
              <Plus size={15} />{" "}
              {tab === "ledger"
                ? "Add entry"
                : tab === "cases"
                  ? "New follow-up"
                  : "New plan"}
            </button>
          )}
        </div>
      </div>
      <CollectionFilters key={tab} control={filter} label={titles[tab] || "Records"} />
      <Failure error={rows.error || (!edit ? error : "")} />
      {tab === "ledger" && rows.summary && (
        <LedgerSummary summary={rows.summary} />
      )}{" "}
      {!rows.loading && rows.items.length > 0 && filter.items.length === 0 && <p role="status">No records match these filters. Clear filters to see all records.</p>}
      {rows.loading ? (
        <p>Loading saved records…</p>
      ) : rows.items.length ? (
        <div className="farm-record-list">
          {filter.items.slice(0, visible).map((r) => (
            <article key={r.id} className={`feature-card notebook-record notebook-record-${tab}`}>
              <div className="farm-section-heading">
                <div>
                  <span className="feature-source">
                    {tab === "ledger" && r.basis === "actual" ? r.kind === "income" ? "Received" : "Paid" : r.status === "synthetic_example" ? localPresentation ? "Crop follow-up" : "Example case" : String(r.status || r.basis || r.kind || "Saved fact").replace(/_/g, " ")}
                    {r.occurred_on ? ` · ${displayDate(r.occurred_on)}` : ""}
                  </span>
                  <>
                    {r.origin && (
                      <ProvenanceBadge
                        value={{ origin: r.origin } as Provenance}
                      />
                    )}
                  </>
                  <h3>
                    {r.title ||
                      r.description ||
                      r.fact_key ||
                      r.key ||
                      r.fact ||
                      "Farm note"}
                  </h3>
                  {tab === "ledger" && (
                    <strong className="farm-ledger-amount">
                      ₹{Number(r.amount_inr).toLocaleString("en-IN")}{" "}
                      <small>{r.kind}</small>
                    </strong>
                  )}
                </div>
                <div className="farm-row-actions">
                  <button
                    aria-label={`Edit ${r.title || r.description || "saved fact"}`}
                    onClick={() =>
                      setEdit({
                        ...r,
                        correction:
                          typeof r.value === "object"
                            ? r.value?.content || ""
                            : r.value || "",
                      })
                    }
                  >
                    <Pencil size={15} />
                  </button>
                  {tab === "ledger" || tab === "memory" ? (
                    <button
                      aria-label={`Review deleting ${r.description || "saved fact"}`}
                      onClick={() =>
                        setExpanded(expanded === r.id ? null : r.id)
                      }
                    >
                      <Trash2 size={15} />
                    </button>
                  ) : null}
                </div>
              </div>
              {r.objective && <p>{r.objective}</p>}
              {r.note && <p>{r.note}</p>}
              {tab === "memory" && (
                <p>
                  {typeof r.value === "object"
                    ? r.value?.content || JSON.stringify(r.value)
                    : r.value || r.content || r.summary}
                </p>
              )}
              {expanded === r.id && (
                <div className="farm-delete-review">
                  <p>
                    {tab === "memory"
                      ? "Forget this saved fact? Its original conversation may still exist."
                      : "Delete this entry from your ledger?"}
                  </p>
                  <button
                    disabled={busy}
                    onClick={() =>
                      void mutate("DELETE", r.id, {
                        row_version: r.row_version,
                      })
                    }
                  >
                    Confirm {tab === "memory" ? "forget" : "delete"}
                  </button>
                  <button onClick={() => setExpanded(null)}>Keep it</button>
                </div>
              )}
              {tab === "missions" && (
                <>
                  <button
                    className="farm-text-action"
                    disabled={
                      assistant.running ||
                      !!assistant.pending ||
                      ["paused", "completed", "cancelled"].includes(r.status)
                    }
                    onClick={() => {
                      onNavigate("chat");
                      void sendAssistant(
                        `Work with me on this farm plan: ${r.title}. Goal: ${r.objective || "Ask me for the goal"}. Remaining steps: ${
                          (r.steps || [])
                            .filter((s: Row) => !s.done)
                            .map((s: Row) => s.title)
                            .join("; ") || "Ask me what I need next"
                        }. Prepare useful files or review actual data where possible, and ask before saving changes.`,
                        { mission_id: r.id, workspace_view: "records" },
                      );
                    }}
                  >
                    Work on this with Mitra <ArrowUpRight size={14} />
                  </button>
                  <p className="feature-footnote">
                    Mitra can prepare files, review data and ask for approval.
                    Equipment and bookings stay manual.
                  </p>
                </>
              )}
              {tab === "missions" && (
                <details className="farm-mission-options">
                  <summary>Manage plan</summary>
                  <div className="farm-mission-controls">
                    {["active", "paused", "completed", "cancelled"]
                      .filter((s) => s !== r.status)
                      .map((status) => (
                        <button
                          disabled={busy}
                          key={status}
                          onClick={() =>
                            void mutate("PATCH", r.id, {
                              title: r.title,
                              objective: r.objective,
                              steps: r.steps,
                              row_version: r.row_version,
                              status,
                            })
                          }
                        >
                          {status === "active"
                            ? "Start / resume"
                            : status === "paused"
                              ? "Pause"
                              : status === "completed"
                                ? "Mark complete"
                                : "Cancel plan"}
                        </button>
                      ))}
                  </div>
                </details>
              )}
              {(tab === "cases" || tab === "missions") && (
                <details
                  className="farm-history"
                  onToggle={(e) => {
                    if (e.currentTarget.open && !history[r.id])
                      void loadHistory(r);
                  }}
                >
                  <summary>
                    {tab === "cases"
                      ? "Dated observations"
                      : "Progress and activity"}
                  </summary>
                  {tab === "missions" &&
                    (r.steps || []).map((step: Row, i: number) => (
                      <label className="farm-step" key={i}>
                        <input
                          type="checkbox"
                          checked={step.done}
                          disabled={
                            busy ||
                            ["cancelled", "completed"].includes(r.status)
                          }
                          onChange={(e) =>
                            void mutate("PATCH", r.id, {
                              title: r.title,
                              objective: r.objective,
                              status: r.status,
                              row_version: r.row_version,
                              steps: r.steps.map((s: Row, n: number) =>
                                n === i ? { ...s, done: e.target.checked } : s,
                              ),
                            })
                          }
                        />
                        {step.title}
                      </label>
                    ))}
                  {history[r.id] ? (
                    history[r.id].length ? (
                      history[r.id].map((n) => (
                        <p key={n.id}>
                          <small>
                            {displayDate(n.observed_on || n.created_at)} ·{" "}
                            {n.action || "Observation"}
                          </small>
                          <br />
                          {n.note ||
                            (typeof n.detail === "object"
                              ? n.detail?.note ||
                                n.detail?.status ||
                                JSON.stringify(n.detail)
                              : n.detail)}
                        </p>
                      ))
                    ) : (
                      <p>No activity recorded yet.</p>
                    )
                  ) : (
                    <p>Loading activity…</p>
                  )}
                </details>
              )}
              {tab === "cases" && (
                <button
                  className="farm-text-action"
                  onClick={() =>
                    setEdit({
                      ...r,
                      add_note: true,
                      observation: "",
                      observed_on: new Intl.DateTimeFormat("en-CA", {
                        timeZone: "Asia/Kolkata",
                        year: "numeric",
                        month: "2-digit",
                        day: "2-digit",
                      }).format(new Date()),
                    })
                  }
                >
                  <Plus size={14} /> Add observation
                </button>
              )}
            </article>
          ))}
        </div>
      ) : (
        <Empty>
          {tab === "memory"
            ? "No saved farm facts yet. You can tell Mitra details you want it to remember."
            : "Nothing saved here yet. Add your first record when you’re ready."}
        </Empty>
      )}
      {filter.items.length > visible && (
        <button
          className="farm-text-action"
          onClick={() => setVisible((n) => n + 5)}
        >
          Show more records ({filter.items.length - visible})
        </button>
      )}
      {tab === "missions" && <SharedFarmWork />}
      {edit && (
        <Editor
          title={
            tab === "memory"
              ? "Correct saved fact"
              : edit.add_note
                ? "Add crop observation"
                : `${edit.id ? "Edit" : "New"} ${tab === "ledger" ? "ledger entry" : tab === "cases" ? "crop follow-up" : "farm plan"}`
          }
          onClose={() => !busy && setEdit(null)}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void saveEdited();
            }}
          >
            <Failure error={error} />
            {tab === "ledger" ? (
              <>
                <Field
                  label="What was it for?"
                  required
                  value={edit.description || ""}
                  onChange={(v) => change("description", v)}
                />
                <Field
                  label="Amount in rupees"
                  type="number"
                  required
                  value={String(edit.amount_inr)}
                  onChange={(v) => change("amount_inr", v)}
                />
                <label className="farm-form-field">
                  Type
                  <select
                    value={edit.kind}
                    onChange={(e) => change("kind", e.target.value)}
                  >
                    {["expense", "income"].map((v) => (
                      <option key={v}>{v}</option>
                    ))}
                  </select>
                </label>
                <label className="farm-form-field">
                  Record basis
                  <select
                    value={edit.basis}
                    onChange={(e) => change("basis", e.target.value)}
                  >
                    <option value="actual">Actual payment / receipt</option>
                    <option value="estimated">Estimate</option>
                    <option
                      value="receivable"
                      disabled={edit.kind !== "income"}
                    >
                      Payment due
                    </option>
                  </select>
                </label>
                <Field
                  label="Date"
                  type="date"
                  required
                  value={edit.occurred_on || ""}
                  onChange={(v) => change("occurred_on", v)}
                />
              </>
            ) : tab === "memory" ? (
              <Field
                label="Corrected fact"
                required
                value={String(edit.correction || "")}
                onChange={(v) => change("correction", v)}
              />
            ) : edit.add_note ? (
              <>
                <Field
                  label="Observation"
                  required
                  value={edit.observation || ""}
                  onChange={(v) => change("observation", v)}
                />
                <Field
                  label="Observed on"
                  required
                  type="date"
                  value={edit.observed_on || ""}
                  onChange={(v) => change("observed_on", v)}
                />
              </>
            ) : (
              <>
                <Field
                  label="Title"
                  required
                  value={edit.title || ""}
                  onChange={(v) => change("title", v)}
                />
                {tab === "cases" && edit.id ? (
                  <label className="farm-form-field">
                    Status
                    <select
                      value={edit.status}
                      onChange={(e) => change("status", e.target.value)}
                    >
                      {["open", "monitoring", "expert_review", "resolved"].map(
                        (status) => (
                          <option key={status}>{status}</option>
                        ),
                      )}
                    </select>
                  </label>
                ) : (
                  <Field
                    label={tab === "cases" ? "Symptoms you noticed" : "Goal"}
                    value={edit.note || edit.objective || ""}
                    onChange={(v) =>
                      change(tab === "cases" ? "note" : "objective", v)
                    }
                  />
                )}
              </>
            )}
            {tab === "missions" && (
              <label className="farm-form-field">
                Steps (one per line)
                <WorkspaceVoiceField
                  label="Speak a plan step"
                  onTranscript={(title) =>
                    setEdit({
                      ...edit,
                      steps: [
                        ...(edit.steps || []),
                        { title, done: false },
                      ].slice(0, 30),
                    })
                  }
                >
                  <textarea
                    aria-label="Plan steps"
                    value={(edit.steps || [])
                      .map((step: Row) => step.title)
                      .join("\n")}
                    onChange={(e) =>
                      setEdit({
                        ...edit,
                        steps: e.target.value
                          .split("\n")
                          .slice(0, 30)
                          .map((title, index) => ({
                            title,
                            done: edit.steps?.[index]?.done || false,
                          })),
                      })
                    }
                  />
                </WorkspaceVoiceField>
              </label>
            )}
            <footer>
              <button
                type="button"
                disabled={busy}
                onClick={() => setEdit(null)}
              >
                Cancel
              </button>
              <button className="feature-primary" disabled={busy}>
                {busy ? "Saving…" : "Save record"}
              </button>
            </footer>
          </form>
        </Editor>
      )}
    </section>
  );
}
function CropSeasons() {
  const cycles = useRows("/api/crop-cycles", "crop_cycles"),
    plots = useRows("/api/plots", "plots");
  const [crops, setCrops] = useState<Row[]>([]),
    [edit, setEdit] = useState<Row | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    void workspaceRequest<Row>("/api/onboarding/options")
      .then((d) => setCrops(d.crops || []))
      .catch((e) => setError(e.message));
  }, []);
  const change = (key: string, value: string) =>
    setEdit((current) => ({ ...current, [key]: value }));
  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!edit) return;
    setBusy(true);
    setError("");
    try {
      await workspaceRequest(
        `/api/crop-cycles${edit.id ? `/${edit.id}` : ""}`,
        edit.id ? "PUT" : "POST",
        {
          plot_id: edit.plot_id,
          crop_id: edit.crop_id,
          variety_id: edit.variety_id || null,
          season: edit.season,
          sowing_date: edit.sowing_date,
          expected_harvest_date: edit.expected_harvest_date || null,
          actual_harvest_date: edit.actual_harvest_date || null,
          status: edit.status,
        },
      );
      setEdit(null);
      cycles.refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <details className="farm-season-section">
      <summary>
        Crop seasons <span>{cycles.items.length}</span>
      </summary>
      <ExportMenu
        filename="my-crop-seasons"
        rows={cycles.items}
        disabled={cycles.loading || !!cycles.error}
        note="Reported crop cycles. Future harvest dates are estimates, not confirmed harvests."
      />
      <div className="farm-section-heading">
        <p>
          Link a crop and sowing date to its field. A future harvest date is
          your estimate.
        </p>
        <button
          className="feature-primary"
          disabled={!plots.items.length}
          onClick={() =>
            setEdit({
              plot_id: plots.items[0]?.id,
              crop_id: crops[0]?.id,
              season: "",
              sowing_date: "",
              expected_harvest_date: "",
              actual_harvest_date: "",
              status: "planned",
            })
          }
        >
          <Plus size={15} /> Add season
        </button>
      </div>
      <Failure error={cycles.error || plots.error || (!edit ? error : "")} />
      {cycles.items.map((c) => (
        <article key={c.id} className="farm-season-row">
          <div>
            <strong>
              {c.crop_name} · {c.season}
            </strong>
            <span>
              {c.status} · sown {c.sowing_date}
              {c.expected_harvest_date
                ? ` · harvest estimate ${c.expected_harvest_date}`
                : ""}
            </span>
          </div>
          <button
            aria-label={`Edit ${c.crop_name} season`}
            onClick={() => setEdit({ ...c })}
          >
            <Pencil size={15} />
          </button>
        </article>
      ))}
      {!cycles.loading && !cycles.items.length && (
        <p className="feature-footnote">
          No crop seasons saved. Add a field first, then its crop.
        </p>
      )}
      {edit && (
        <Editor
          title={`${edit.id ? "Edit" : "Add"} crop season`}
          onClose={() => !busy && setEdit(null)}
        >
          <form onSubmit={save}>
            <Failure error={error} />
            <label className="farm-form-field">
              Field
              <select
                required
                value={edit.plot_id}
                onChange={(e) => change("plot_id", e.target.value)}
              >
                {plots.items.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name || "Saved field"} · {p.area_ha} ha
                  </option>
                ))}
              </select>
            </label>
            <label className="farm-form-field">
              Crop
              <select
                required
                value={edit.crop_id}
                onChange={(e) => {
                  setEdit({
                    ...edit,
                    crop_id: e.target.value,
                    variety_id: null,
                  });
                }}
              >
                {crops.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
            <Field
              label="Season name"
              required
              value={edit.season}
              onChange={(v) => change("season", v)}
            />
            <Field
              label="Sowing date"
              required
              type="date"
              value={edit.sowing_date}
              onChange={(v) => change("sowing_date", v)}
            />
            <Field
              label="Expected harvest date"
              type="date"
              value={edit.expected_harvest_date || ""}
              onChange={(v) => change("expected_harvest_date", v)}
            />
            <label className="farm-form-field">
              Crop status
              <select
                value={edit.status}
                onChange={(e) => change("status", e.target.value)}
              >
                {["planned", "growing", "harvested", "failed"].map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </label>
            {edit.status === "harvested" && (
              <Field
                label="Actual harvest date"
                required
                type="date"
                value={edit.actual_harvest_date || ""}
                onChange={(v) => change("actual_harvest_date", v)}
              />
            )}
            <footer>
              <button
                type="button"
                onClick={() => setEdit(null)}
                disabled={busy}
              >
                Cancel
              </button>
              <button className="feature-primary" disabled={busy}>
                {busy ? "Saving…" : "Save season"}
              </button>
            </footer>
          </form>
        </Editor>
      )}
    </details>
  );
}

function WeatherContext() {
  const [data, setData] = useState<Row | null>(null);
  useEffect(() => {
    let active = true;
    void workspaceRequest<Row>("/api/farm-workspace/weather-brief")
      .then((d) => {
        if (active) setData(d);
      })
      .catch(() => {
        if (active)
          setData({
            available: false,
            note: "Weather context could not be loaded. Check the station or ask Mitra for a dated forecast.",
          });
      });
    return () => {
      active = false;
    };
  }, []);
  return data ? (
    <details className="farm-history">
      <summary>Weather context</summary>
      <ProvenanceBadge value={data.provenance} />
      <p>{data.note}</p>
      {(data.signals || []).slice(0, 3).map((signal: Row, i: number) => (
        <p key={i}>
          <strong>{signal.title}</strong>
          <br />
          {signal.detail}
          <small> · {signal.date}</small>
        </p>
      ))}
      {data.available && !data.signals?.length && (
        <p>
          No additional weather flags in this dated forecast. Check its dates
          before planning field work.
        </p>
      )}
    </details>
  ) : null;
}

function LedgerSummary({ summary }: { summary: Row }) {
  const money = (value: unknown) =>
    `₹${Number(value || 0).toLocaleString("en-IN")}`;
  return (
    <div className="farm-ledger-summary">
      {summary.includes_demo_fixtures && (
        <ProvenanceBadge value={{ origin: "synthetic" }} />
      )}
      <div>
        {[
          ["Money received", "actual_income"],
          ["Costs paid", "actual_expense"],
          ["Recorded balance", "recorded_balance"],
        ].map(([title, key]) => (
          <span key={key}>
            <small>{title}</small>
            <strong>{money(summary[key])}</strong>
          </span>
        ))}
      </div>
      <details>
        <summary>Estimates and payments due</summary>
        <p>
          Estimated income {money(summary.estimated_income)} · Estimated costs{" "}
          {money(summary.estimated_expense)} · Payments due{" "}
          {money(summary.receivable)}
        </p>
      </details>
      <details className="journal-balance-note"><summary>How the balance works</summary><p className="feature-footnote">
        {summary.note ||
          "Recorded entries only. Missing costs and sales are not inferred; estimates and payments due are excluded from the balance."}
      </p></details>
    </div>
  );
}
function FarmWeather({ farm, plots }: { farm: Row; plots: Row[] }) {
  const [plotId, setPlotId] = useState(plots[0]?.id || ""),
    [consent, setConsent] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  useEffect(() => {
    if (!plotId && plots.length) setPlotId(plots[0].id);
  }, [plots, plotId]);
  async function changeLink(remove = false) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await workspaceRequest(
        `/api/farms/${farm.id}/weather-link`,
        remove ? "DELETE" : "POST",
        remove
          ? undefined
          : { plot_id: plotId, consent_to_share_coarse_grid: true },
      );
      setNotice(
        remove
          ? "Weather sharing stopped for this farm. Existing dated records remain."
          : "Weather sharing enabled. New forecasts will appear when the source worker retrieves them.",
      );
      if (remove) setConsent(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <details className="farm-history">
      <summary>Weather for this farm</summary>
      <p>
        Choose a field and allow its approximate 0.25° grid location to be
        shared with the public weather provider. Exact coordinates stay in your
        farm record.
      </p>
      <Failure error={error} />
      <label className="farm-form-field">
        Forecast location
        <select value={plotId} onChange={(e) => setPlotId(e.target.value)}>
          {plots.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name || "Saved field"} · {p.area_ha} ha
            </option>
          ))}
        </select>
      </label>
      <label className="farm-weather-consent">
        <input
          type="checkbox"
          checked={consent}
          onChange={(e) => setConsent(e.target.checked)}
        />{" "}
        I agree to share this approximate location for weather forecasts.
      </label>
      <div className="farm-mission-controls">
        <button
          disabled={!plotId || !consent || busy}
          onClick={() => void changeLink()}
        >
          Enable weather sharing
        </button>
        <button disabled={busy} onClick={() => void changeLink(true)}>
          Stop sharing
        </button>
      </div>
      {notice && <p role="status">{notice}</p>}
    </details>
  );
}
function FarmTimeline() {
  const [open, setOpen] = useState(false);
  return (
    <details
      className="farm-season-section"
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary>Your farm timeline</summary>
      {open && <TimelineRecords />}
    </details>
  );
}
function TimelineRecords() {
  const records = useRows("/api/farm-workspace/timeline?limit=30", "items");
  return (
    <>
      <Failure error={records.error} />
      <ExportMenu
        filename="my-farm-timeline"
        rows={records.items}
        disabled={records.loading || !!records.error}
        note="Most recent 30 dated records loaded in this timeline."
      />
      <p className="feature-footnote">
        Dated reports and records. Calendar dates describe plans; they do not
        prove work was performed.
      </p>
      {records.loading ? (
        <p>Loading your farm history…</p>
      ) : records.items.length ? (
        <ol className="farm-timeline">
          {records.items.map((r) => (
            <li key={`${r.kind}:${r.id}`}>
              <time>{displayDate(r.occurred_at)}</time>
              <strong>{r.title}</strong>
              <span>
                {r.kind.replace(/_/g, " ")}
                {r.detail?.status ? ` · ${r.detail.status}` : ""}
              </span>
              {r.detail?.origin && (
                <ProvenanceBadge value={{ origin: r.detail.origin }} />
              )}
            </li>
          ))}
        </ol>
      ) : (
        <Empty>No dated farm records yet.</Empty>
      )}
    </>
  );
}
