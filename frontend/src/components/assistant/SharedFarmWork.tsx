import { ExportMenu } from "./ExportMenu";
import { useEffect, useState } from "react";
import { Plus, Pencil, X, Copy, Check } from "lucide-react";
import * as Dialog from "@radix-ui/react-dialog";
import { WorkspaceVoiceField } from "@/components/WorkspaceVoiceField";
import { parseSpokenNumber, parseSpokenDate } from "@/lib/voiceNumbers";
import { workspaceRequest } from "@/lib/farmWorkspaceClient";
import "./shared-farm-work.css";

function Problem({ message }: { message: string }) {
  return message ? (
    <p className="workspace-error" role="alert">
      {message}
    </p>
  ) : null;
}
function EditDialog({
  title,
  children,
  onClose,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
}) {
  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="farm-editor-overlay" />
        <Dialog.Content
          className="farm-editor farm-editor-modal"
          aria-describedby={undefined}
        >
          <header>
            <Dialog.Title asChild>
              <h2>{title}</h2>
            </Dialog.Title>
            <button type="button" aria-label="Close editor" onClick={onClose}>
              <X size={18} />
            </button>
          </header>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
function TextField({
  label,
  value,
  onChange,
  required = false,
  type = "text",
  dictate = true,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  type?: string;
  dictate?: boolean;
}) {
  const [error, setError] = useState("");
  const input = (
    <input
      aria-label={label}
      type={type}
      value={value}
      required={required}
      step={type === "number" ? "0.01" : undefined}
      onChange={(e) => onChange(e.target.value)}
    />
  );
  return (
    <div className="farm-form-field">
      <label>
        {label}
        {dictate ? (
          <WorkspaceVoiceField
            label={`Speak ${label.toLowerCase()}`}
            onTranscript={(text) => {
              try {
                onChange(
                  type === "number"
                    ? String(
                        parseSpokenNumber(text, { unit: "rupees", min: 0 }),
                      )
                    : type === "date"
                      ? parseSpokenDate(text)
                      : text,
                );
                setError("");
              } catch (e) {
                setError((e as Error).message);
              }
            }}
          >
            {input}
          </WorkspaceVoiceField>
        ) : (
          input
        )}
      </label>
      <Problem message={error} />
    </div>
  );
}
export function SharedFarmWork() {
  const [servicesOpen, setServicesOpen] = useState(false),
    [groupsOpen, setGroupsOpen] = useState(false);
  return (
    <div className="shared-farm-work">
      <details
        className="farm-season-section"
        onToggle={(e) => setServicesOpen(e.currentTarget.open)}
      >
        <summary>Your service notebook</summary>
        {servicesOpen && <ServiceNotebook />}
      </details>
      <details
        className="farm-season-section"
        onToggle={(e) => setGroupsOpen(e.currentTarget.open)}
      >
        <summary>Family &amp; FPO plans</summary>
        {groupsOpen && <GroupNotebook />}
      </details>
    </div>
  );
}
interface ServiceRecord {
  id: string;
  title: string;
  service_type: "labour" | "machinery" | "transport" | "expert" | "other";
  supplier: string;
  quote_inr: number | null;
  scheduled_on: string | null;
  notes: string;
  status:
    | "planned"
    | "requested"
    | "quote_recorded"
    | "farmer_confirmed"
    | "farmer_completed"
    | "cancelled";
  row_version: number;
  updated_at: string;
}
interface Group {
  id: string;
  name: string;
  role: "owner" | "contributor" | "reader";
}
interface SharedTask {
  id: string;
  title: string;
  notes: string;
  due_on: string | null;
  completed: boolean;
  row_version: number;
}
interface Member {
  farmer_id: string;
  display_name: string;
  role: Group["role"];
}
interface Invitation {
  id: string;
  role: "reader" | "contributor";
  expires_at: string;
  used: boolean;
  revoked?: boolean;
}
function useCollection<T>(path: string) {
  const [items, setItems] = useState<T[]>([]),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [revision, setRevision] = useState(0);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    void workspaceRequest<{ items: T[] }>(path)
      .then((d) => {
        if (alive) setItems(d.items || []);
      })
      .catch((e) => {
        if (alive) setError(e.message);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [path, revision]);
  return { items, error, loading, refresh: () => setRevision((n) => n + 1) };
}
const serviceStatuses: Record<ServiceRecord["status"], string> = {
  planned: "Planning",
  requested: "Request recorded",
  quote_recorded: "Quote recorded",
  farmer_confirmed: "You confirmed the arrangement",
  farmer_completed: "You marked it complete",
  cancelled: "Cancelled",
};
function ServiceNotebook() {
  const records = useCollection<ServiceRecord>(
    "/api/farm-workspace/service-requests",
  );
  const [edit, setEdit] = useState<Partial<ServiceRecord> | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const change = (key: keyof ServiceRecord, value: string) =>
    setEdit((current) => ({ ...current, [key]: value }));
  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!edit) return;
    setBusy(true);
    setError("");
    try {
      await workspaceRequest(
        `/api/farm-workspace/service-requests${edit.id ? `/${edit.id}` : ""}`,
        edit.id ? "PATCH" : "POST",
        {
          title: edit.title,
          service_type: edit.service_type,
          supplier: edit.supplier || "",
          quote_inr:
            edit.quote_inr === null ||
            edit.quote_inr === undefined ||
            String(edit.quote_inr) === ""
              ? null
              : Number(edit.quote_inr),
          scheduled_on: edit.scheduled_on || null,
          notes: edit.notes || "",
          status: edit.status,
          ...(edit.id ? { row_version: edit.row_version } : {}),
        },
      );
      setEdit(null);
      records.refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="shared-notebook-heading">
        <p>
          Keep labour, machinery, transport and expert arrangements in your own
          notebook. Supplier details and quotes are entered by you; this doesn’t
          send a request or book a service.
        </p>
        <button
          className="feature-primary"
          onClick={() => {
            setError("");
            setEdit({
              title: "",
              service_type: "other",
              supplier: "",
              quote_inr: null,
              scheduled_on: null,
              notes: "",
              status: "planned",
            });
          }}
        >
          <Plus size={14} /> Add arrangement
        </button>
      </div>
      <ExportMenu
        filename="my-service-arrangements"
        rows={records.items}
        disabled={records.loading || !!records.error}
        note="Private farmer-entered arrangements and quotes; these records do not prove bookings or payments."
      />
      <Problem message={records.error} />
      {records.loading ? (
        <p className="feature-footnote">Loading your service notes…</p>
      ) : records.items.length ? (
        records.items.map((r) => (
          <article className="shared-entry" key={r.id}>
            <header>
              <div>
                <small>
                  {r.service_type} · {serviceStatuses[r.status]}
                </small>
                <h3>{r.title}</h3>
              </div>
              <button
                aria-label={`Edit arrangement ${r.title}`}
                onClick={() => {
                  setError("");
                  setEdit({ ...r });
                }}
              >
                <Pencil size={15} />
              </button>
            </header>
            {r.supplier && <p>{r.supplier}</p>}
            {r.quote_inr !== null && (
              <div className="shared-quote">
                ₹{Number(r.quote_inr).toLocaleString("en-IN")}{" "}
                <small>quote you recorded</small>
              </div>
            )}
            {r.scheduled_on && <small>Planned for {r.scheduled_on}</small>}
            {r.notes && <p>{r.notes}</p>}
          </article>
        ))
      ) : (
        <p className="feature-footnote">No service arrangements saved yet.</p>
      )}
      {edit && (
        <EditDialog
          title={
            edit.id ? "Edit service arrangement" : "New service arrangement"
          }
          onClose={() => !busy && setEdit(null)}
        >
          <form onSubmit={save}>
            <Problem message={error} />
            <TextField
              label="Arrangement title"
              required
              value={edit.title || ""}
              onChange={(v) => change("title", v)}
            />
            <label className="farm-form-field">
              Service type
              <select
                value={edit.service_type}
                onChange={(e) => change("service_type", e.target.value)}
              >
                {["labour", "machinery", "transport", "expert", "other"].map(
                  (type) => (
                    <option key={type}>{type}</option>
                  ),
                )}
              </select>
            </label>
            <TextField
              label="Supplier or contact name"
              required={[
                "quote_recorded",
                "farmer_confirmed",
                "farmer_completed",
              ].includes(edit.status || "")}
              value={edit.supplier || ""}
              onChange={(v) => change("supplier", v)}
            />
            <TextField
              label="Quote in rupees"
              required={edit.status === "quote_recorded"}
              type="number"
              value={
                edit.quote_inr === null || edit.quote_inr === undefined
                  ? ""
                  : String(edit.quote_inr)
              }
              onChange={(v) =>
                setEdit({ ...edit, quote_inr: v === "" ? null : Number(v) })
              }
            />
            <TextField
              label="Planned service date"
              type="date"
              value={edit.scheduled_on || ""}
              onChange={(v) => change("scheduled_on", v)}
            />
            <label className="farm-form-field">
              Your arrangement status
              <select
                value={edit.status}
                onChange={(e) => change("status", e.target.value)}
              >
                {Object.entries(serviceStatuses).map(([status, label]) => (
                  <option key={status} value={status}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <TextField
              label="Your notes"
              value={edit.notes || ""}
              onChange={(v) => change("notes", v)}
            />
            <p className="feature-footnote">
              Confirming here records your statement. It is not supplier
              verification or an external booking.
            </p>
            <div className="shared-form-actions">
              <button
                type="button"
                disabled={busy}
                onClick={() => setEdit(null)}
              >
                Cancel
              </button>
              <button className="feature-primary" disabled={busy}>
                {busy ? "Saving…" : "Save arrangement"}
              </button>
            </div>
          </form>
        </EditDialog>
      )}
    </>
  );
}
function GroupNotebook() {
  const groups = useCollection<Group>("/api/farm-workspace/groups");
  const [selected, setSelected] = useState(""),
    [dialog, setDialog] = useState<"create" | "join" | null>(null),
    [name, setName] = useState(""),
    [code, setCode] = useState(""),
    [review, setReview] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    if (!selected && groups.items.length) setSelected(groups.items[0].id);
  }, [groups.items, selected]);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await workspaceRequest<Group>(
        dialog === "join"
          ? "/api/farm-workspace/groups/join"
          : "/api/farm-workspace/groups",
        "POST",
        dialog === "join"
          ? { code: code.trim(), consent_to_share_display_name: true }
          : { name: name.trim() },
      );
      setSelected(result.id);
      groups.refresh();
      setDialog(null);
      setCode("");
      setName("");
      setReview(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const group = groups.items.find((g) => g.id === selected);
  return (
    <>
      <div className="shared-notebook-heading">
        <p>
          A small shared checklist for your family or FPO. Members see group
          plans and display names. Your private farm ledger, fields, locations,
          crop cases and conversations stay private.
        </p>
        <div className="shared-group-controls">
          <button
            onClick={() => {
              setDialog("create");
              setError("");
            }}
          >
            New group
          </button>
          <button
            onClick={() => {
              setDialog("join");
              setError("");
              setReview(false);
            }}
          >
            Join with a code
          </button>
        </div>
      </div>
      <Problem message={groups.error} />
      {groups.loading ? (
        <p className="feature-footnote">Loading shared groups…</p>
      ) : groups.items.length ? (
        <>
          <label className="farm-form-field">
            Your shared group
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
            >
              {groups.items.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name} · {g.role}
                </option>
              ))}
            </select>
          </label>
          {group && <GroupPlans key={group.id} group={group} />}
        </>
      ) : (
        <p className="feature-footnote">
          No shared groups yet. Create one or use a code someone shares with
          you.
        </p>
      )}
      {dialog && (
        <EditDialog
          title={
            dialog === "join" ? "Join a shared group" : "Create a shared group"
          }
          onClose={() => !busy && setDialog(null)}
        >
          <form onSubmit={submit}>
            <Problem message={error} />
            {dialog === "create" ? (
              <TextField
                label="Group name"
                required
                value={name}
                onChange={setName}
              />
            ) : (
              <>
                <TextField
                  dictate={false}
                  label="Invitation code"
                  required
                  value={code}
                  onChange={setCode}
                />
                <label className="shared-invite-review">
                  <input
                    type="checkbox"
                    checked={review}
                    onChange={(e) => setReview(e.target.checked)}
                  />{" "}
                  I agree to share my display name with this group and access
                  its shared plans. My private farm records won’t be shared.
                </label>
              </>
            )}
            <div className="shared-form-actions">
              <button
                type="button"
                onClick={() => setDialog(null)}
                disabled={busy}
              >
                Cancel
              </button>
              <button
                className="feature-primary"
                disabled={busy || (dialog === "join" && !review)}
              >
                {busy
                  ? "Saving…"
                  : dialog === "join"
                    ? "Join this group"
                    : "Create group"}
              </button>
            </div>
          </form>
        </EditDialog>
      )}
    </>
  );
}
function GroupPlans({ group }: { group: Group }) {
  const path = `/api/farm-workspace/groups/${group.id}`;
  const tasks = useCollection<SharedTask>(`${path}/tasks`);
  const [edit, setEdit] = useState<Partial<SharedTask> | null>(null),
    [inviting, setInviting] = useState(false),
    [role, setRole] = useState<"reader" | "contributor">("reader"),
    [review, setReview] = useState(false),
    [receipt, setReceipt] = useState<{
      code: string;
      expires_at: string;
    } | null>(null),
    [copied, setCopied] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const canEdit = group.role !== "reader";
  async function saveTask(e: React.FormEvent) {
    e.preventDefault();
    if (!edit) return;
    setBusy(true);
    setError("");
    try {
      await workspaceRequest(
        `${path}/tasks${edit.id ? `/${edit.id}` : ""}`,
        edit.id ? "PATCH" : "POST",
        {
          title: edit.title,
          notes: edit.notes || "",
          due_on: edit.due_on || null,
          ...(edit.id
            ? { completed: edit.completed, row_version: edit.row_version }
            : {}),
        },
      );
      setEdit(null);
      tasks.refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function mark(task: SharedTask, completed: boolean) {
    setBusy(true);
    setError("");
    try {
      await workspaceRequest(`${path}/tasks/${task.id}`, "PATCH", {
        title: task.title,
        notes: task.notes || "",
        due_on: task.due_on,
        completed,
        row_version: task.row_version,
      });
      tasks.refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function invite(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await workspaceRequest<{
        code: string;
        expires_at: string;
      }>(`${path}/invites`, "POST", {
        role,
        consent_to_share_group_plans: true,
      });
      setReceipt(result);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="shared-group-plans">
      <div className="shared-notebook-heading">
        <p>
          {group.role === "reader"
            ? "You can read this group’s plans. An owner can invite you as a contributor to edit them."
            : "Work together on just this checklist. Marking a task complete records a member’s statement; it doesn’t operate equipment."}
        </p>
        <div className="shared-group-controls">
          <ExportMenu
            filename="shared-farm-checklist"
            rows={tasks.items}
            disabled={tasks.loading || !!tasks.error}
            note={`Checklist shared with members of ${group.name}. Download contains only this authorised group’s loaded tasks, no invitation codes or private farm records.`}
          />
          {canEdit && (
            <button
              onClick={() => {
                setError("");
                setEdit({
                  title: "",
                  notes: "",
                  due_on: null,
                  completed: false,
                });
              }}
            >
              <Plus size={13} /> Add shared task
            </button>
          )}
          {group.role === "owner" && (
            <button
              onClick={() => {
                setError("");
                setInviting(true);
                setReview(false);
                setReceipt(null);
                setCopied(false);
              }}
            >
              Invite someone
            </button>
          )}
        </div>
      </div>
      <Problem message={tasks.error || (!edit && !inviting ? error : "")} />
      {tasks.loading ? (
        <p className="feature-footnote">Loading shared tasks…</p>
      ) : tasks.items.length ? (
        tasks.items.map((t) => (
          <div className="shared-task" key={t.id}>
            <input
              type="checkbox"
              aria-label={`Complete ${t.title}`}
              checked={t.completed}
              disabled={!canEdit || busy}
              onChange={(e) => void mark(t, e.target.checked)}
            />
            <span>
              {t.title}
              {t.notes && <small> · {t.notes}</small>}
              {t.due_on && <small> · due {t.due_on}</small>}
            </span>
            {canEdit && (
              <button
                type="button"
                className="farm-text-action"
                aria-label={`Edit shared task ${t.title}`}
                onClick={() => {
                  setError("");
                  setEdit({ ...t });
                }}
              >
                <Pencil size={14} />
              </button>
            )}
          </div>
        ))
      ) : (
        <p className="feature-footnote">No shared tasks saved yet.</p>
      )}
      <GroupAccess group={group} />
      {edit && (
        <EditDialog
          title={edit.id ? "Edit shared task" : "Add shared task"}
          onClose={() => !busy && setEdit(null)}
        >
          <form onSubmit={saveTask}>
            <Problem message={error} />
            <TextField
              label="Shared task title"
              required
              value={edit.title || ""}
              onChange={(title) => setEdit({ ...edit, title })}
            />
            <TextField
              label="Shared task notes"
              value={edit.notes || ""}
              onChange={(notes) => setEdit({ ...edit, notes })}
            />
            <TextField
              label="Due date"
              type="date"
              value={edit.due_on || ""}
              onChange={(due_on) => setEdit({ ...edit, due_on })}
            />
            <div className="shared-form-actions">
              <button
                type="button"
                onClick={() => setEdit(null)}
                disabled={busy}
              >
                Cancel
              </button>
              <button className="feature-primary" disabled={busy}>
                {busy ? "Saving…" : "Save shared task"}
              </button>
            </div>
          </form>
        </EditDialog>
      )}
      {inviting && (
        <EditDialog
          title={receipt ? "Your invitation code" : "Invite to shared plans"}
          onClose={() => {
            if (!busy) {
              setInviting(false);
              setReceipt(null);
            }
          }}
        >
          {receipt ? (
            <>
              <p className="feature-footnote">
                This code can be used once, within seven days. Only share it
                with the person you want in this group.
              </p>
              <div className="shared-invite-code">{receipt.code}</div>
              <p className="feature-footnote">
                Expires{" "}
                {new Date(receipt.expires_at).toLocaleString("en-IN", {
                  timeZone: "Asia/Kolkata",
                })}
              </p>
              <div className="shared-form-actions">
                <button
                  type="button"
                  className="feature-primary"
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(receipt.code);
                      setCopied(true);
                    } catch {
                      setError(
                        "Copy is unavailable. Select and copy the code yourself.",
                      );
                    }
                  }}
                >
                  {copied ? <Check size={14} /> : <Copy size={14} />}{" "}
                  {copied ? "Copied" : "Copy code"}
                </button>
              </div>
              <Problem message={error} />
            </>
          ) : (
            <form onSubmit={invite}>
              <Problem message={error} />
              <label className="farm-form-field">
                Access to this group
                <select
                  value={role}
                  onChange={(e) =>
                    setRole(e.target.value as "reader" | "contributor")
                  }
                >
                  <option value="reader">Reader · view shared plans</option>
                  <option value="contributor">
                    Contributor · add and edit shared tasks
                  </option>
                </select>
              </label>
              <label className="shared-invite-review">
                <input
                  type="checkbox"
                  checked={review}
                  onChange={(e) => setReview(e.target.checked)}
                />{" "}
                I understand this shares this group’s plans and member display
                names. Private farm records and conversations stay private.
              </label>
              <p className="feature-footnote">
                You’ll get a code to share yourself. Mitra won’t message anyone.
              </p>
              <div className="shared-form-actions">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => setInviting(false)}
                >
                  Cancel
                </button>
                <button className="feature-primary" disabled={busy || !review}>
                  {busy ? "Creating…" : "Create invitation code"}
                </button>
              </div>
            </form>
          )}
        </EditDialog>
      )}
    </div>
  );
}
function GroupAccess({ group }: { group: Group }) {
  const [open, setOpen] = useState(false);
  return (
    <details
      className="farm-history"
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary>Members and access</summary>
      {open && <AccessRecords group={group} />}
    </details>
  );
}
function AccessRecords({ group }: { group: Group }) {
  const path = `/api/farm-workspace/groups/${group.id}`;
  const members = useCollection<Member>(`${path}/members`);
  const [invites, setInvites] = useState<Invitation[]>([]),
    [review, setReview] = useState<{
      kind: "member" | "invite";
      id: string;
    } | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function refreshInvites() {
    if (group.role !== "owner") return;
    try {
      const result = await workspaceRequest<{ items: Invitation[] }>(
        `${path}/invites`,
      );
      setInvites(result.items || []);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    void refreshInvites();
  }, [group.id, group.role]);
  async function revoke() {
    if (!review) return;
    setBusy(true);
    setError("");
    try {
      await workspaceRequest(
        `${path}/${review.kind === "member" ? "members" : "invites"}/${review.id}`,
        "DELETE",
      );
      setReview(null);
      members.refresh();
      void refreshInvites();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Problem message={members.error || error} />
      <div className="shared-members">
        {members.items.map((m) => (
          <div key={m.farmer_id}>
            {m.display_name || "Member"} · {m.role}
            {group.role === "owner" && m.role !== "owner" && (
              <button
                className="farm-text-action"
                onClick={() => setReview({ kind: "member", id: m.farmer_id })}
              >
                Remove access
              </button>
            )}
          </div>
        ))}
      </div>
      {group.role === "owner" && invites.length > 0 && (
        <details>
          <summary>Invitation access</summary>
          {invites.map((i) => (
            <p className="feature-footnote" key={i.id}>
              {i.role} ·{" "}
              {i.revoked
                ? "Revoked"
                : i.used
                  ? "Used"
                  : new Date(i.expires_at).getTime() < Date.now()
                    ? "Expired"
                    : "Unused"}{" "}
              · expires {new Date(i.expires_at).toLocaleDateString("en-IN")}
              {!i.used &&
                !i.revoked &&
                new Date(i.expires_at).getTime() > Date.now() && (
                  <button
                    className="farm-text-action"
                    onClick={() => setReview({ kind: "invite", id: i.id })}
                  >
                    Revoke code
                  </button>
                )}
            </p>
          ))}
        </details>
      )}
      {review && (
        <div className="farm-delete-review">
          <p>
            {review.kind === "member"
              ? "Remove this member’s access to this group?"
              : "Revoke this invitation code? It will no longer allow joining."}
          </p>
          <button disabled={busy} onClick={() => void revoke()}>
            Confirm revoke
          </button>
          <button disabled={busy} onClick={() => setReview(null)}>
            Keep access
          </button>
        </div>
      )}
    </>
  );
}
