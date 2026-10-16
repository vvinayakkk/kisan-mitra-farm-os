import { WorkspaceVoiceField } from "@/components/WorkspaceVoiceField";
import { ExportMenu } from "./ExportMenu";
import { useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Plus,
  Check,
  Pencil,
  Trash2,
  X,
  Leaf,
} from "lucide-react";
import {
  useAssistant,
  sendAssistant,
  changeTask,
  type FarmTask,
} from "@/lib/assistantClient";
import { MitraHelper } from "./MitraHelper";

const key = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
export function FarmCalendar({ onChat }: { onChat: () => void }) {
  const state = useAssistant();
  const [month, setMonth] = useState(() => new Date());
  const [selected, setSelected] = useState(() => key(new Date()));
  const [showDeleted, setShowDeleted] = useState(false);
  const [editing, setEditing] = useState<FarmTask | null>(null);
  const [removed, setRemoved] = useState<FarmTask | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const start = new Date(month.getFullYear(), month.getMonth(), 1);
  start.setDate(1 - ((start.getDay() + 6) % 7));
  const days = Array.from(
    { length: 42 },
    (_, i) =>
      new Date(start.getFullYear(), start.getMonth(), start.getDate() + i),
  );
  const tasks = state.tasks.filter((t) => t.due_date === selected);
  const today = key(new Date());
  const disabled = saving || state.running || !!state.pending;
  const ask = (text: string) => {
    onChat();
    void sendAssistant(text);
  };
  async function mutate(task: FarmTask, action: "edit" | "delete" | "restore") {
    setSaving(true);
    setError("");
    try {
      await changeTask(task, action);
      if (action === "edit") setEditing(null);
      if (action === "delete") setRemoved(task);
      if (action === "restore") setRemoved(null);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Your change could not be saved.",
      );
    } finally {
      setSaving(false);
    }
  }
  return (
    <section className="farm-calendar" aria-label="Farm calendar">
      <header className="calendar-heading">
        <div>
          <span className="mitra-eyebrow">YOUR FARM PLAN</span>
          <h1>Your season, one day at a time.</h1>
          <p>
            {state.tasks.filter((t) => !t.completed).length} open tasks · A
            little room for what matters
          </p>
        </div>
        <div className="calendar-header-actions">
          <ExportMenu
            filename="farm-calendar"
            rows={state.tasks}
            columns={[
              { key: "title", label: "Task" },
              { key: "due_date", label: "Date" },
              { key: "notes", label: "Notes" },
              { key: "completed", label: "Completed" },
            ]}
          />
          <button
            aria-label="Deleted tasks"
            aria-expanded={showDeleted}
            onClick={() => setShowDeleted((v) => !v)}
          >
            <Trash2 size={14} />
            <span>Deleted</span>
          </button>
          <button
            disabled={disabled}
            onClick={() =>
              ask(
                `Help me add a farm task for ${selected}. Ask what I need to do.`,
              )
            }
          >
            <Plus size={14} /> Add task
          </button>
        </div>
      </header>
      <div className="calendar-layout">
        <div className="calendar-month">
          <div className="calendar-heading">
            <button
              aria-label="Previous month"
              onClick={() =>
                setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))
              }
            >
              <ChevronLeft size={17} />
            </button>
            <strong>
              {month.toLocaleDateString(undefined, {
                month: "long",
                year: "numeric",
              })}
            </strong>
            <button
              aria-label="Next month"
              onClick={() =>
                setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))
              }
            >
              <ChevronRight size={17} />
            </button>
          </div>
          <div className="calendar-weekdays">
            {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
              <span key={d}>{d}</span>
            ))}
          </div>
          <div className="calendar-grid">
            {days.map((d) => {
              const date = key(d);
              return (
                <button
                  key={date}
                  aria-label={date}
                  aria-pressed={selected === date}
                  onClick={() => {
                    setSelected(date);
                    setEditing(null);
                  }}
                  className={`calendar-day ${d.getMonth() !== month.getMonth() ? "outside" : ""} ${date === today ? "today" : ""} ${date === selected ? "selected" : ""}`}
                >
                  <span>{d.getDate()}</span>
                  {state.tasks
                    .filter((t) => t.due_date === date)
                    .slice(0, 2)
                    .map((t) => (
                      <small key={t.id}>
                        {t.completed ? "✓ " : ""}
                        {t.title}
                      </small>
                    ))}
                </button>
              );
            })}
          </div>
          <p className="calendar-note">
            Saved plans appear here. Notifications and hardware actions are not
            scheduled.
          </p>
        </div>
        <aside className="calendar-agenda" aria-label="Selected day">
          <span className="mitra-eyebrow">A DAY IN YOUR FIELD</span>
          <h2>
            {new Date(selected + "T12:00:00").toLocaleDateString(undefined, {
              weekday: "long",
              month: "long",
              day: "numeric",
            })}
          </h2>
          {tasks.length === 0 ? (
            <div className="calendar-empty">
              <Leaf size={24} />
              <p>No tasks planned for this day.</p>
              <small>Let Mitra help you make a little progress.</small>
            </div>
          ) : (
            tasks.map((t) => (
              <article key={t.id} className="calendar-task">
                <div>
                  <strong>{t.title}</strong>
                  <p>{t.notes || "Your saved farm task"}</p>
                </div>
                <div className="calendar-task-actions">
                  {t.completed ? (
                    <span>
                      <Check size={13} /> Done
                    </span>
                  ) : (
                    <button
                      disabled={disabled}
                      onClick={() =>
                        void mutate({ ...t, completed: true }, "edit")
                      }
                    >
                      Mark done
                    </button>
                  )}
                  <button
                    disabled={disabled}
                    aria-label={`Edit ${t.title}`}
                    onClick={() => setEditing({ ...t })}
                  >
                    <Pencil size={14} /> Edit
                  </button>
                  <button
                    disabled={disabled}
                    aria-label={`Delete ${t.title}`}
                    onClick={() => void mutate(t, "delete")}
                  >
                    <Trash2 size={14} /> Delete
                  </button>
                </div>
              </article>
            ))
          )}
          {editing && (
            <form
              className="calendar-edit-form"
              onSubmit={(e) => {
                e.preventDefault();
                void mutate(editing, "edit");
              }}
            >
              <header>
                <strong>Edit task</strong>
                <button
                  type="button"
                  aria-label="Close task editor"
                  onClick={() => setEditing(null)}
                >
                  <X size={15} />
                </button>
              </header>
              <label htmlFor="calendar-task-name">
                Task name
                <WorkspaceVoiceField
                  disabled={disabled}
                  label="Speak task name"
                  onTranscript={(title) => setEditing({ ...editing, title })}
                >
                  <input
                    id="calendar-task-name"
                    aria-label="Task name"
                    required
                    maxLength={200}
                    value={editing.title}
                    onChange={(e) =>
                      setEditing({ ...editing, title: e.target.value })
                    }
                  />
                </WorkspaceVoiceField>
              </label>
              <label>
                Date
                <input
                  required
                  type="date"
                  value={editing.due_date}
                  onChange={(e) =>
                    setEditing({ ...editing, due_date: e.target.value })
                  }
                />
              </label>
              <label htmlFor="calendar-task-notes">
                Notes
                <WorkspaceVoiceField
                  disabled={disabled}
                  label="Speak task notes"
                  onTranscript={(notes) => setEditing({ ...editing, notes })}
                >
                  <textarea
                    id="calendar-task-notes"
                    aria-label="Notes"
                    maxLength={2000}
                    value={editing.notes ?? ""}
                    onChange={(e) =>
                      setEditing({ ...editing, notes: e.target.value })
                    }
                  />
                </WorkspaceVoiceField>
              </label>
              <button disabled={disabled} type="submit">
                {saving ? "Saving…" : "Save changes"}
              </button>
            </form>
          )}
          {showDeleted && (
            <section className="calendar-deleted">
              <strong>Deleted tasks</strong>
              {(state.deletedTasks ?? []).length === 0 ? (
                <p>No deleted tasks.</p>
              ) : (
                (state.deletedTasks ?? []).map((task) => (
                  <article key={task.id}>
                    <span>{task.title}</span>
                    <button
                      disabled={disabled}
                      onClick={() => void mutate(task, "restore")}
                    >
                      Restore
                    </button>
                  </article>
                ))
              )}
            </section>
          )}
          {removed && (
            <div className="calendar-undo" role="status">
              <span>Task removed.</span>
              <button
                disabled={saving || state.running}
                onClick={() => void mutate(removed, "restore")}
              >
                Undo
              </button>
            </div>
          )}
          {error && (
            <p role="alert" className="mitra-error">
              {error}
            </p>
          )}
          <MitraHelper context="calendar" selectedDate={selected} />
        </aside>
      </div>
    </section>
  );
}
