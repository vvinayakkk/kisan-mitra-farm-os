import { useEffect, useRef, useState } from "react";
import {
  ArrowUpRight,
  Check,
  ChevronLeft,
  ChevronRight,
  Database,
  Download,
  FileClock,
  Leaf,
  LogOut,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Upload,
  Users,
  X,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  adminRequest,
  Column,
  csvText,
  fieldValue,
  Operation,
  parseCsv,
  Preview,
  Resource,
  Row,
  rowOperation,
} from "@/lib/adminClient";
import {
  confirmPhoneCode,
  currentIdentityUid,
  sendPhoneCode,
  signOutPhone,
  watchPhoneIdentity,
} from "@/lib/firebasePhoneAuth";
import "./admin.css";
const show = (v: unknown) =>
  v === null || v === undefined
    ? "—"
    : typeof v === "object"
      ? JSON.stringify(v)
      : String(v);
const label = (s: string) =>
  s.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
function download(name: string, content: string, type = "text/csv") {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function changedFields(change: Preview["changes"][number]) {
  return [
    ...new Set([
      ...Object.keys(change.before || {}),
      ...Object.keys(change.after || {}),
    ]),
  ].filter(
    (key) =>
      key !== "_version" &&
      JSON.stringify(change.before?.[key]) !==
        JSON.stringify(change.after?.[key]),
  );
}
function Buddy() {
  return (
    <div className="admin-buddy" aria-hidden="true">
      <span>• ‿ •</span>
      <Leaf size={18} />
    </div>
  );
}
export default function Admin() {
  const [identity, setIdentity] = useState(0),
    [me, setMe] = useState<{ role: string; subject: string } | null>(null),
    [resources, setResources] = useState<Resource[]>([]),
    [name, setName] = useState("overview"),
    [page, setPage] = useState(1),
    [search, setSearch] = useState(""),
    [query, setQuery] = useState(""),
    [farmer, setFarmer] = useState(""),
    [rows, setRows] = useState<Row[]>([]),
    [total, setTotal] = useState(0),
    [selected, setSelected] = useState<Set<number>>(new Set()),
    [revision, setRevision] = useState(0),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [mode, setMode] = useState<
      "edit" | "create" | "bulk" | "import" | null
    >(null),
    [editing, setEditing] = useState<Row | null>(null),
    [form, setForm] = useState<Record<string, string>>({}),
    [reason, setReason] = useState(""),
    [bulkField, setBulkField] = useState(""),
    [bulkValue, setBulkValue] = useState(""),
    [importText, setImportText] = useState(""),
    [preview, setPreview] = useState<Preview | null>(null),
    [confirmation, setConfirmation] = useState("");
  const [phone, setPhone] = useState(""),
    [code, setCode] = useState(""),
    [sent, setSent] = useState(false),
    [online, setOnline] = useState(navigator.onLine);
  const [counts, setCounts] = useState<Record<string, number> | null>(null);
  const epoch = useRef(0);
  const resource = resources.find((r) => r.name === name);
  const isAudit = name === "audit";
  const isOverview = name === "overview";
  useEffect(() => {
    const changed = () => {
      epoch.current++;
      setMe(null);
      setResources([]);
      setCounts(null);
      setRows([]);
      setPreview(null);
      setMode(null);
      setSelected(new Set());
      setIdentity((v) => v + 1);
    };
    const stop = watchPhoneIdentity(changed);
    const net = () => setOnline(navigator.onLine);
    window.addEventListener("online", net);
    window.addEventListener("offline", net);
    return () => {
      stop();
      window.removeEventListener("online", net);
      window.removeEventListener("offline", net);
      epoch.current++;
    };
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setError("");
    void adminRequest<{ role: string; subject: string }>(
      "/me",
      undefined,
      controller.signal,
    )
      .then(async (user) => {
        const data = await adminRequest<{ resources: Resource[] }>(
          "/resources",
          undefined,
          controller.signal,
        );
        if (!controller.signal.aborted) {
          setMe(user);
          setResources(data.resources);
        }
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      });
    return () => controller.abort();
  }, [identity]);
  useEffect(() => {
    const timer = setTimeout(() => {
      setQuery(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    if (!me || isOverview) return;
    const controller = new AbortController();
    setLoading(true);
    setError("");
    setRows([]);
    setSelected(new Set());
    const path = isAudit
      ? `/audit?page=${page}`
      : `/resources/${name}?page=${page}&search=${encodeURIComponent(query)}${farmer ? "&farmer_id=" + encodeURIComponent(farmer) : ""}`;
    void adminRequest<{ records: Row[]; total: number }>(
      path,
      undefined,
      controller.signal,
    )
      .then((data) => {
        if (!controller.signal.aborted) {
          setRows(data.records);
          setTotal(data.total);
        }
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [me, name, page, query, farmer, revision]);
  useEffect(() => {
    if (!me || !isOverview) return;
    const controller = new AbortController();
    void adminRequest<{ counts: Record<string, number> }>(
      "/overview",
      undefined,
      controller.signal,
    )
      .then((data) => {
        if (!controller.signal.aborted) setCounts(data.counts);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      });
    return () => controller.abort();
  }, [me, isOverview, revision]);
  function navigate(next: string, owner = "") {
    setName(next);
    setPage(1);
    setSearch("");
    setQuery("");
    setFarmer(owner);
    setNotice("");
    setSelected(new Set());
    setMode(null);
    setPreview(null);
  }
  const editable = resource?.columns.filter((c) => c.editable) || [];
  const createColumns =
    resource?.columns.filter(
      (c) =>
        !c.generated &&
        ![
          "created_at",
          "updated_at",
          "row_version",
          "contact_verified_at",
          "profile_key",
        ].includes(c.name) &&
        !(c.primary_key && c.default),
    ) || [];
  function open(next: typeof mode, row?: Row) {
    setEditing(row || null);
    setForm({});
    setReason("");
    setMode(next);
    setError("");
    setBulkField(editable[0]?.name || "");
    setBulkValue("");
    setImportText("");
  }
  async function review(operations: Operation[]) {
    if (!resource || busy) return;
    setBusy(true);
    setError("");
    const owner = epoch.current;
    try {
      const result = await adminRequest<Preview>(
        `/resources/${resource.name}/preview`,
        { operations, reason },
      );
      if (owner === epoch.current) {
        setPreview(result);
        setConfirmation("");
        setMode(null);
      }
    } catch (e) {
      if (owner === epoch.current) setError((e as Error).message);
    } finally {
      if (owner === epoch.current) setBusy(false);
    }
  }
  function submit() {
    try {
      if (!resource) return;
      let operations: Operation[] = [];
      if (mode === "import") {
        operations = parseCsv(importText).map((row) => ({
          action: "create",
          values: Object.fromEntries(
            Object.entries(row)
              .filter(([, v]) => v !== "")
              .map(([k, v]) => {
                const column = createColumns.find((c) => c.name === k);
                if (!column)
                  throw new Error(`Unknown or protected column: ${k}`);
                return [k, fieldValue(column, v)];
              }),
          ),
        }));
      } else if (mode === "bulk") {
        const column = editable.find((c) => c.name === bulkField);
        if (!column) throw new Error("Choose a field.");
        operations = [...selected].map((i) =>
          rowOperation(resource, rows[i], "update", {
            [bulkField]: fieldValue(column, bulkValue),
          }),
        );
      } else {
        const values = Object.fromEntries(
          Object.entries(form).map(([k, v]) => [
            k,
            fieldValue(
              resource.columns.find((c) => c.name === k)!,
              v,
            ),
          ]),
        );
        operations = [
          mode === "edit" && editing
            ? rowOperation(resource, editing, "update", values)
            : { action: "create", values },
        ];
      }
      void review(operations);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function apply() {
    if (!preview || busy) return;
    setBusy(true);
    setError("");
    const owner = epoch.current;
    try {
      const result = await adminRequest<{ status: string }>(
        `/previews/${preview.id}/commit`,
        { confirmation },
      );
      if (owner === epoch.current) {
        setNotice(
          result.status === "already_applied"
            ? "This batch was already applied."
            : "Changes saved. The audit log has been updated.",
        );
        setPreview(null);
        setRevision((v) => v + 1);
      }
    } catch (e) {
      if (owner === epoch.current) setError((e as Error).message);
    } finally {
      if (owner === epoch.current) setBusy(false);
    }
  }
  async function login() {
    setBusy(true);
    setError("");
    try {
      if (sent) {
        await confirmPhoneCode(code);
        setIdentity((v) => v + 1);
      } else {
        await sendPhoneCode(phone);
        setSent(true);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function logout() {
    epoch.current++;
    setMe(null);
    setResources([]);
    setCounts(null);
    setRows([]);
    setPreview(null);
    setMode(null);
    await signOutPhone();
  }
  const priority = [
    "display_name",
    "name",
    "title",
    "status",
    "preferred_language",
    "contact_phone",
    "due_at",
    "amount_inr",
    "created_at",
  ];
  const columns = isAudit
    ? ["created_at", "resource", "role", "reason"]
    : resource
      ? [...resource.columns]
          .sort(
            (a, b) =>
              (priority.includes(a.name) ? priority.indexOf(a.name) : 100) -
              (priority.includes(b.name) ? priority.indexOf(b.name) : 100),
          )
          .slice(0, 5)
          .map((c) => c.name)
      : [];
  const editColumns = mode === "create" ? createColumns : editable;
  if (!me)
    return (
      <div className="admin-shell admin-login">
        <section>
          <Buddy />
          <span className="admin-eyebrow">MITRA / ADMINISTRATION</span>
          <h1>
            A little care.
            <br />
            For the whole community.
          </h1>
          <p>Manage people, farm data and the services they rely on.</p>
          <label>
            Administrator phone number
            <input
              autoComplete="tel"
              type="tel"
              placeholder="+91…"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
            />
          </label>
          {sent && (
            <label>
              Verification code
              <input
                autoComplete="one-time-code"
                value={code}
                onChange={(e) => setCode(e.target.value)}
              />
            </label>
          )}
          <button
            className="admin-primary"
            disabled={busy || !online}
            onClick={login}
          >
            {busy
              ? "Checking…"
              : sent
                ? "Verify and continue"
                : "Send sign-in code"}
          </button>
          {error && (
            <p role="alert" className="admin-error">
              {error}
            </p>
          )}
          <p className="admin-muted">
            <ShieldCheck size={16} /> Access is granted to approved accounts
            only.
          </p>
          <a href="/workspace">Back to your farm</a>
          {currentIdentityUid() && (
            <button onClick={logout}>Use another account</button>
          )}
        </section>
      </div>
    );
  return (
    <div className="admin-shell">
      <aside className="admin-nav">
        <a className="admin-brand" href="/workspace">
          <Buddy />
          <span>
            mitra<span>ADMINISTRATION</span>
          </span>
        </a>
        <button
          className={isOverview ? "active" : ""}
          onClick={() => navigate("overview")}
        >
          <SlidersHorizontal size={18} /> Control room
        </button>
        {Object.entries(
          resources.reduce(
            (a, r) => ({ ...a, [r.group]: [...(a[r.group] || []), r] }),
            {} as Record<string, Resource[]>,
          ),
        ).map(([group, items]) => (
          <details key={group} open={resource?.group === group}>
            <summary>{group}</summary>
            {items?.map((r) => (
              <button
                key={r.name}
                className={name === r.name ? "active" : ""}
                onClick={() => navigate(r.name)}
              >
                {r.name === "farmers" ? (
                  <Users size={16} />
                ) : (
                  <Database size={15} />
                )}
                <span>{r.label}</span>
                {!r.writable && (
                  <span className="admin-read" aria-hidden="true">
                    ↗
                  </span>
                )}
              </button>
            ))}
          </details>
        ))}
        <button
          className={isAudit ? "active" : ""}
          onClick={() => navigate("audit")}
        >
          <FileClock size={18} /> Admin audit log
        </button>
        <div className="admin-nav-foot">
          <ShieldCheck size={17} />
          <span>{label(me.role)} access</span>
          <button aria-label="Sign out" onClick={logout}>
            <LogOut size={17} />
          </button>
        </div>
      </aside>
      <main className="admin-main">
        <header className="admin-top">
          <span>YOUR COMMUNITY, WELL CARED FOR</span>
          <span className={online ? "admin-status" : "admin-error"}>
            <i />
            {online ? "Connected" : "Offline · changes paused"}
          </span>
        </header>
        <div className="admin-heading">
          <div>
            <span className="admin-eyebrow">
              {isAudit
                ? "ACCOUNTABILITY"
                : isOverview
                  ? "MITRA CONTROL ROOM"
                  : resource?.group.toUpperCase()}
            </span>
            <h1>
              {isAudit
                ? "Every change, accounted for."
                : isOverview
                  ? "Good things grow with care."
                  : resource?.label}
            </h1>
            <p>
              {isAudit
                ? "Who changed what, when and why. Audit entries cannot be edited."
                : isOverview
                  ? "One calm place to look after your farmers and their data."
                  : name === "farmers"
                    ? "The people at the heart of Mitra. Open a profile to help them along."
                    : "Explore, maintain and review the records that power your farmers’ experience."}
            </p>
          </div>
          <Buddy />
        </div>
        {error && !mode && !preview && (
          <div role="alert" className="admin-error">
            {error}
            <button onClick={() => setRevision((v) => v + 1)}>Try again</button>
          </div>
        )}
        {notice && (
          <div role="status" className="admin-success">
            <Check size={17} />
            {notice}
          </div>
        )}
        {isOverview ? (
          <>
            <div className="admin-stats">
              {["farmers", "farms", "tasks", "exchange_listings"].map((key) => (
                <button key={key} onClick={() => navigate(key)}>
                  <span>{label(key)}</span>
                  <strong>
                    {counts ? counts[key]?.toLocaleString() : "—"}
                  </strong>
                  <small>View records ↗</small>
                </button>
              ))}
            </div>
            <div className="admin-overview">
              {[
                [
                  "People",
                  "farmers",
                  "Look after your community",
                  "Profiles, account status, fields and farm tasks.",
                ],
                [
                  "Knowledge & markets",
                  "price_observations",
                  "Keep information useful",
                  "Prices, crops, guides and government schemes.",
                ],
                [
                  "Weather & stations",
                  "weather_forecasts",
                  "See what’s happening outside",
                  "Forecasts, soil records and connected stations.",
                ],
                [
                  "Activity",
                  "agent_runs",
                  "Understand the journey",
                  "Conversations, agent activity and source health.",
                ],
              ].map(([group, target, title, description]) => (
                <button
                  key={group}
                  onClick={() =>
                    navigate(
                      resources.some((r) => r.name === target)
                        ? target
                        : resources.find((r) => r.group === group)?.name ||
                            "farmers",
                    )
                  }
                >
                  <span className="admin-eyebrow">{group}</span>
                  <h2>{title}</h2>
                  <p>{description}</p>
                  <ArrowUpRight />
                </button>
              ))}
            </div>
            <section className="admin-care">
              <Buddy />
              <div>
                <h2>A thoughtful change starts with a review.</h2>
                <p>
                  Import up to 100 records at a time, check the exact changes,
                  then apply them together. Every saved batch has a reason and a
                  permanent audit entry.
                </p>
              </div>
            </section>
          </>
        ) : (
          <>
            <section className="admin-data">
              <div className="admin-toolbar">
                {!isAudit && (
                  <label className="admin-search">
                    <Search size={17} />
                    <input
                      aria-label="Search records"
                      placeholder="Search these records…"
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                    />
                  </label>
                )}
                <div className="admin-actions">
                  <button
                    disabled={loading}
                    aria-label="Refresh records"
                    onClick={() => setRevision((v) => v + 1)}
                  >
                    <RefreshCw size={17} />
                  </button>
                  <button
                    disabled={!rows.length || loading}
                    onClick={() =>
                      download(
                        `${name}-page-${page}.csv`,
                        csvText(
                          rows,
                          isAudit
                            ? [
                                "id",
                                "created_at",
                                "actor",
                                "role",
                                "resource",
                                "reason",
                                "changes",
                              ]
                            : resource!.columns.map((c) => c.name),
                        ),
                      )
                    }
                  >
                    <Download size={16} /> Export page
                  </button>
                  {resource?.writable && name !== "farmers" && (
                    <>
                      <button
                        disabled={!online || loading}
                        onClick={() => open("import")}
                      >
                        <Upload size={16} /> Import CSV
                      </button>
                      <button
                        disabled={!online || loading}
                        className="admin-primary"
                        onClick={() => open("create")}
                      >
                        <Plus size={17} /> Add record
                      </button>
                    </>
                  )}
                </div>
              </div>
              {farmer && (
                <div className="admin-filter">
                  Farmer: {farmer}
                  <button
                    onClick={() => {
                      setFarmer("");
                      setPage(1);
                    }}
                  >
                    Clear filter <X size={14} />
                  </button>
                </div>
              )}
              {!!selected.size && (
                <div className="admin-selection">
                  <strong>{selected.size} selected on this page</strong>
                  <button onClick={() => open("bulk")}>Update selected</button>
                  {resource?.deletable && (
                    <button
                      className="admin-danger"
                      onClick={() => {
                        open("bulk");
                        setBulkField("__delete");
                      }}
                    >
                      Delete selected
                    </button>
                  )}
                  <button onClick={() => setSelected(new Set())}>Clear</button>
                </div>
              )}
              <div className="admin-table-wrap" aria-busy={loading}>
                <table>
                  <thead>
                    <tr>
                      {resource?.writable && (
                        <th>
                          <input
                            type="checkbox"
                            aria-label="Select page"
                            checked={
                              rows.length > 0 && selected.size === rows.length
                            }
                            onChange={(e) =>
                              setSelected(
                                new Set(
                                  e.target.checked ? rows.map((_, i) => i) : [],
                                ),
                              )
                            }
                          />
                        </th>
                      )}
                      {columns.map((c) => (
                        <th key={c}>{label(c)}</th>
                      ))}
                      <th>
                        <span className="sr-only">Details</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, i) => (
                      <tr
                        key={
                          resource
                            ? resource.primary_key
                                .map((k) => show(row[k]))
                                .join(":")
                            : show(row.id)
                        }
                      >
                        {resource?.writable && (
                          <td>
                            <input
                              type="checkbox"
                              aria-label={`Select record ${i + 1}`}
                              checked={selected.has(i)}
                              onChange={(e) =>
                                setSelected((old) => {
                                  const next = new Set(old);
                                  if (e.target.checked) next.add(i);
                                  else next.delete(i);
                                  return next;
                                })
                              }
                            />
                          </td>
                        )}
                        {columns.map((c, j) => (
                          <td key={c} title={show(row[c])}>
                            {c === "status" ? (
                              <span className={`admin-pill ${show(row[c])}`}>
                                {show(row[c])}
                              </span>
                            ) : j === 0 ? (
                              <strong>{show(row[c])}</strong>
                            ) : (
                              show(row[c])
                            )}
                          </td>
                        ))}
                        <td>
                          <button
                            aria-label={`Open record ${i + 1}`}
                            onClick={() => open("edit", row)}
                          >
                            <ArrowUpRight size={17} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {loading ? (
                  <div className="admin-empty" role="status">
                    Opening records…
                  </div>
                ) : (
                  !rows.length && (
                    <div className="admin-empty">
                      <Database />
                      <h2>
                        {query ? "No matching records" : "No records here yet"}
                      </h2>
                      <p>
                        {query
                          ? "Try a different search."
                          : resource?.writable && name !== "farmers"
                            ? "Add a record or import a CSV to get started."
                            : "Records appear here as people use Mitra and data sources sync."}
                      </p>
                    </div>
                  )
                )}
              </div>
              <footer className="admin-pagination">
                <span>
                  {total.toLocaleString()} records · page {page} of{" "}
                  {Math.max(1, Math.ceil(total / 25))}
                </span>
                <div>
                  <button
                    aria-label="Previous page"
                    disabled={page === 1 || loading}
                    onClick={() => setPage((v) => v - 1)}
                  >
                    <ChevronLeft size={18} />
                  </button>
                  <button
                    aria-label="Next page"
                    disabled={page * 25 >= total || loading}
                    onClick={() => setPage((v) => v + 1)}
                  >
                    <ChevronRight size={18} />
                  </button>
                </div>
              </footer>
            </section>
            <p className="admin-footnote">
              <ShieldCheck size={15} />
              {resource?.writable
                ? "Changes require a preview and confirmation. Linked records are protected."
                : "Read-only records preserve the original activity and provenance."}
            </p>
          </>
        )}
      </main>
      <Dialog
        open={!!mode}
        onOpenChange={(v) => {
          if (!v && !busy) setMode(null);
        }}
      >
        <DialogContent className="admin-dialog">
          <DialogTitle>
            {mode === "create"
              ? "A new record"
              : mode === "import"
                ? "Bring your data into Mitra"
                : mode === "bulk"
                  ? bulkField === "__delete"
                    ? "Review selected deletions"
                    : "Update selected records"
                  : isAudit
                    ? "Audit entry"
                    : "Record details"}
          </DialogTitle>
          <DialogDescription>
            {mode === "import"
              ? "Upload CSV with column names as headers. Up to 100 rows; blank cells use database defaults. Type null for an explicit empty value."
              : "Review the details below. Changes are checked before anything is saved."}
          </DialogDescription>
          {mode === "edit" && editing && (
            <>
              <dl className="admin-details">
                {Object.entries(editing)
                  .filter(([k]) => k !== "_version")
                  .map(([k, v]) => (
                    <div key={k}>
                      <dt>{label(k)}</dt>
                      <dd>{show(v)}</dd>
                    </div>
                  ))}
              </dl>
              {name === "farmers" && (
                <div className="admin-related">
                  {[
                    "farms",
                    "plots",
                    "tasks",
                    "expenses",
                    "farm_missions",
                    "companion_proposals",
                    "conversations",
                    "agent_runs",
                  ]
                    .filter((n) => resources.some((r) => r.name === n))
                    .map((n) => (
                      <button
                        key={n}
                        onClick={() => navigate(n, show(editing.id))}
                      >
                        {label(n)} <ArrowUpRight size={14} />
                      </button>
                    ))}
                </div>
              )}
            </>
          )}
          {(mode === "create" || (mode === "edit" && resource?.writable)) && (
            <div className="admin-form">
              {editColumns.map((c) => (
                <label key={c.name}>
                  {label(c.name)}
                  {!c.nullable && !c.default && mode === "create" ? " *" : ""}
                  <textarea
                    rows={/JSON/i.test(c.type) ? 3 : 1}
                    placeholder={
                      mode === "edit"
                        ? show(editing?.[c.name])
                        : c.default
                          ? "Default: " + c.default
                          : c.type
                    }
                    value={form[c.name] ?? ""}
                    onChange={(e) =>
                      setForm((old) => ({ ...old, [c.name]: e.target.value }))
                    }
                  />
                  <small>
                    {c.references.length
                      ? "Links to " + c.references.join(", ")
                      : c.type}
                    {c.nullable ? " · type null to clear" : ""}
                  </small>
                </label>
              ))}
            </div>
          )}
          {mode === "bulk" &&
            (bulkField === "__delete" ? (
              <p className="admin-error">
                Delete {selected.size} records permanently. Linked records will
                block deletion. You will review the exact records next.
              </p>
            ) : (
              <div className="admin-form">
                <label>
                  Field
                  <select
                    aria-label="Field"
                    value={bulkField}
                    onChange={(e) => setBulkField(e.target.value)}
                  >
                    {editable.map((c) => (
                      <option key={c.name} value={c.name}>
                        {label(c.name)}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  New value
                  <textarea
                    value={bulkValue}
                    onChange={(e) => setBulkValue(e.target.value)}
                    placeholder="Use null to clear an optional field"
                  />
                </label>
              </div>
            ))}
          {mode === "import" && (
            <>
              <button
                onClick={() =>
                  download(
                    `${name}-template.csv`,
                    csvText(
                      [],
                      createColumns
                        .filter((c) => !c.default)
                        .map((c) => c.name),
                    ),
                  )
                }
              >
                <Download size={16} /> Download column template
              </button>
              <input
                aria-label="Import CSV file"
                type="file"
                accept=".csv,text/csv"
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  if (file.size > 500000) {
                    setError("Use a file smaller than 500 KB.");
                    return;
                  }
                  setImportText(await file.text());
                }}
              />
              <textarea
                className="admin-import"
                aria-label="CSV contents"
                placeholder="Or paste CSV here…"
                value={importText}
                onChange={(e) => setImportText(e.target.value)}
              />
            </>
          )}
          {(mode !== "edit" || resource?.writable) && (
            <>
              <label className="admin-reason">
                Reason for this change
                <textarea
                  value={reason}
                  maxLength={500}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Help the next administrator understand why…"
                />
              </label>
              <button
                className="admin-primary"
                disabled={busy || !online || reason.trim().length < 5}
                onClick={() =>
                  bulkField === "__delete" && mode === "bulk"
                    ? review(
                        [...selected].map((i) =>
                          rowOperation(resource!, rows[i], "delete"),
                        ),
                      )
                    : submit()
                }
              >
                {busy ? "Checking changes…" : "Preview changes"}
                <ChevronRight size={16} />
              </button>
            </>
          )}
          {error && (
            <p role="alert" className="admin-error">
              {error}
            </p>
          )}
        </DialogContent>
      </Dialog>
      <Dialog
        open={!!preview}
        onOpenChange={(v) => {
          if (!v && !busy) setPreview(null);
        }}
      >
        <DialogContent className="admin-dialog admin-preview">
          <DialogTitle>One last look.</DialogTitle>
          <DialogDescription>
            {preview?.notice} This preview expires in 10 minutes.
          </DialogDescription>
          <div className="admin-change-list">
            {preview?.changes.map((change, i) => (
              <article key={i}>
                <header>
                  <span className="admin-pill">{change.action}</span>
                  <strong>
                    {show(
                      change.before?.display_name ||
                        change.before?.name ||
                        change.before?.title ||
                        change.after?.name ||
                        `Record ${i + 1}`,
                    )}
                  </strong>
                </header>
                <div className="admin-diff">
                  <div>
                    <h3>Before</h3>
                    <dl>
                      {changedFields(change).map((key) => (
                        <div key={key}>
                          <dt>{label(key)}</dt>
                          <dd>
                            {change.before
                              ? show(change.before[key])
                              : "New record"}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                  <div>
                    <h3>After</h3>
                    <dl>
                      {changedFields(change).map((key) => (
                        <div key={key}>
                          <dt>{label(key)}</dt>
                          <dd>
                            {change.after
                              ? show(change.after[key])
                              : "Permanently deleted"}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                </div>
              </article>
            ))}
          </div>
          <label className="admin-reason">
            Type <strong>{preview?.confirmation}</strong> to save
            <input
              autoComplete="off"
              value={confirmation}
              onChange={(e) => setConfirmation(e.target.value)}
            />
          </label>
          <button
            className="admin-primary"
            disabled={busy || !online || confirmation !== preview?.confirmation}
            onClick={apply}
          >
            {busy ? "Applying…" : "Apply reviewed changes"}
            <Check size={17} />
          </button>
          {error && (
            <p role="alert" className="admin-error">
              {error}
            </p>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
