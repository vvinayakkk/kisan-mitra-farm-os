import { createPortal } from "react-dom";
import * as Dialog from "@radix-ui/react-dialog";
import { offlineEnabled } from "@/lib/offlineStore";
import {
  storeAttachmentDraft,
  listAttachmentDrafts,
  readAttachmentDraft,
  removeAttachmentDraft,
  type AttachmentDraft,
} from "@/lib/attachmentDrafts";
import { parseSpokenNumber, parseSpokenDate } from "@/lib/voiceNumbers";
import { AnswerActions } from "./AnswerActions";
import { useLocalDraft } from "@/hooks/useLocalDraft";
import { CompanionPanel, CompanionAvatar } from "./CompanionPanel";
import { unlockSpeechAudio } from "@/lib/speechAudio";
import { LiveConversation } from "./LiveConversation";
import { VoiceInput } from "@/components/VoiceInput";
import { WorkspaceVoiceField } from "@/components/WorkspaceVoiceField";
import { suggestions, type FarmContext } from "./suggestions";
import { memo, useEffect, useRef, useState } from "react";
import { FarmResult } from "./FarmResult";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ArrowUp,
  ArrowRight,
  Check,
  ChevronDown,
  Download,
  Leaf,
  Loader2,
  Square,
  AlertCircle,
  Sparkles,
  FileText,
  Plus,
  X,
  Wrench,
  Paperclip,
  History,
} from "lucide-react";
import {
  rewriteAssistantAnswer,
  downloadArtifact,
  getAssistantSessionId,
  initializeAssistant,
  newConversation,
  sendAssistant,
  stopAssistant,
  useAssistant,
  uploadAttachment,
  restoreConversation,
  type Attachment,
  type Pending,
  type ChatMessage,
} from "@/lib/assistantClient";
import "./assistant.css";
function ReviewValue({ value }: { value: unknown }) {
  if (Array.isArray(value))
    return (
      <ul className="approval-values">
        {value.slice(0, 36).map((item, index) => (
          <li key={index}>
            <ReviewValue value={item} />
          </li>
        ))}
      </ul>
    );
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    if (record.title)
      return (
        <span>
          {String(record.title)}
          {record.done ? " · completed" : ""}
        </span>
      );
    if (record.property)
      return (
        <span>
          <strong>{String(record.property).replace(/_/g, " ")}</strong> ·{" "}
          {String(record.value)} {String(record.unit_code)}
          <small>
            {" "}
            {String(record.reported_basis)} · depth{" "}
            {String(record.depth_top_cm)}–{String(record.depth_bottom_cm)} cm
          </small>
        </span>
      );
    return (
      <span>
        {Object.entries(record)
          .slice(0, 20)
          .map(([key, item]) => (
            <span key={key}>
              {key.replace(/_/g, " ")}: <ReviewValue value={item} /> ·{" "}
            </span>
          ))}
      </span>
    );
  }
  return (
    <span>
      {value === null || value === undefined || value === ""
        ? "Not provided"
        : typeof value === "boolean"
          ? value
            ? "Yes"
            : "No"
          : String(value)}
    </span>
  );
}

function FarmerQuestion({ pending }: { pending: Pending }) {
  const workspace = useAssistant();
  const tasks = workspace.tasks;
  const photos = workspace.attachments.filter((file) =>
    ["jpg", "jpeg", "png", "webp"].includes(file.format),
  );
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [step, setStep] = useState(0);
  const fields = pending.arguments.fields ?? [];
  const field = fields[step];
  const setAnswer = (id: string, value: string) => {
    setValues((previous) => ({ ...previous, [id]: value }));
    setError("");
  };
  if (pending.kind === "approval")
    return (
      <section className="mitra-question">
        <div className="question-heading">
          <Check size={16} /> Review before saving
        </div>
        <p>
          {(
            {
              save_task: "Add this task to your farm plan?",
              record_expense: "Save this expense to your records?",
              update_task: "Save these changes to your task?",
              delete_task:
                "Remove this task from your plan? It can be restored.",
              complete_task: "Mark this task complete?",
              record_ledger: "Save this entry to your farm ledger?",
              create_crop_case: "Open this crop follow-up?",
              record_crop_note: "Save this dated crop observation?",
              create_mission: "Save this longer farm plan?",
              record_service:
                "Save your service arrangement? No booking or payment is made.",
              create_farm_group:
                "Create this private group checklist? No one is invited yet.",
              create_shared_task:
                "Save this task for the selected group’s members to see?",
              save_soil_report:
                "Save these report values? Check sample date, depth, units and nutrient basis. This does not verify the laboratory.",
            } as Record<string, string>
          )[pending.tool] || "Save this reviewed change?"}
        </p>
        <dl>
          {Object.entries(pending.arguments).map(([k, v]) => (
            <div key={k}>
              <dt>
                {(
                  {
                    task_id: "Task",
                    plot_id: "Field",
                    group_id: "Group",
                    case_id: "Crop follow-up",
                    attachment_id: "Source report",
                    amount_inr: "Amount (rupees)",
                    quote_inr: "Quoted amount (rupees)",
                  } as Record<string, string>
                )[k] || k.replace(/_/g, " ")}
              </dt>
              <dd>
                {pending.review_labels?.[k] ||
                  (k === "task_id" ? (
                    tasks.find((t) => t.id === v)?.title || "Selected farm task"
                  ) : (
                    <ReviewValue value={v} />
                  ))}
              </dd>
            </div>
          ))}
        </dl>
        <div className="question-actions">
          <button
            onClick={() =>
              void sendAssistant("Approved", {
                approval: true,
                pending_id: pending.id,
              })
            }
          >
            {pending.tool === "delete_task"
              ? "Remove task"
              : pending.tool === "update_task"
                ? "Save changes"
                : "Save it"}{" "}
            <Check size={13} />
          </button>
          <button
            className="secondary"
            onClick={() =>
              void sendAssistant("Do not save this", {
                approval: false,
                pending_id: pending.id,
              })
            }
          >
            Cancel
          </button>
        </div>
      </section>
    );
  return (
    <form
      className="mitra-question mitra-question-flow"
      onSubmit={(e) => {
        e.preventDefault();
        if (field && !values[field.id]?.trim()) {
          setError("Add this detail to continue.");
          return;
        }
        if (step < fields.length - 1) {
          setStep((current) => current + 1);
          setError("");
          return;
        }
        void sendAssistant(
          fields
            .map(
              (answerField) =>
                `${answerField.label}: ${answerField.type === "photo" ? "Photo attached" : values[answerField.id]}`,
            )
            .join(" · "),
          { answers: values, pending_id: pending.id },
        );
      }}
    >
      <div className="question-topline">
        <div className="question-heading"><Sparkles size={15} /> MITRA IS GETTING THE DETAILS</div>
        {fields.length > 0 && <span className="question-count">{String(step + 1).padStart(2, "0")} <span>/ {String(fields.length).padStart(2, "0")}</span></span>}
      </div>
      {fields.length > 1 && (
        <div className="question-progress" aria-label={`Question ${step + 1} of ${fields.length}`}>
          {fields.map((item, index) => (
            <span key={item.id} className={index < step ? "done" : index === step ? "current" : ""} />
          ))}
        </div>
      )}
      {pending.arguments.question && <p className="question-context">{pending.arguments.question}</p>}
      {field && (
        <div className="question-active-field" key={field.id}>
          {field.type === "select" ? (
            <fieldset className="question-choice-group">
              <legend className="question-prompt">{field.label.replace(/\s*\(e\.g\.,[^)]*\)/i, "")}</legend>
              <div className="question-choices">
                {field.options?.map((option) => (
                  <button
                    key={option}
                    type="button"
                    aria-pressed={values[field.id] === option}
                    onClick={() => setAnswer(field.id, option)}
                  >
                    <span>{option}</span>
                    {values[field.id] === option && <Check size={15} />}
                  </button>
                ))}
              </div>
              <label className="question-entry">
                <span>Or type your own answer</span>
                <input maxLength={500} value={values[field.id] || ""} onChange={event => setAnswer(field.id, event.target.value)} placeholder="Your answer, in your own words" />
              </label>
            </fieldset>
          ) : field.type === "photo" ? (
            <label className="question-entry">
              <span className="question-prompt">{field.label.replace(/\s*\(e\.g\.,[^)]*\)/i, "")}</span>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                required={!values[field.id]}
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  try {
                    const uploaded = await uploadAttachment(file);
                    setAnswer(field.id, uploaded.id);
                  } catch (error) {
                    setError(
                      error instanceof Error
                        ? error.message
                        : "This photo could not be uploaded.",
                    );
                  }
                }}
              />
              {photos.length > 0 && (
                <select
                  aria-label={`Choose an uploaded photo for ${field.label}`}
                  value={values[field.id] || ""}
                  onChange={(event) => setAnswer(field.id, event.target.value)}
                >
                  <option value="">Or choose a photo already uploaded</option>
                  {photos.map((photo) => (
                    <option key={photo.id} value={photo.id}>
                      {photo.name}
                    </option>
                  ))}
                </select>
              )}
            </label>
          ) : (
            <label className="question-entry">
              <span className="question-prompt">{field.label.replace(/\s*\(e\.g\.,[^)]*\)/i, "")}</span>
              <WorkspaceVoiceField
                label={`Speak ${field.label}`}
                onTranscript={(text) => {
                  try {
                    const value =
                      field.type === "number"
                        ? String(parseSpokenNumber(text))
                        : field.type === "date"
                          ? parseSpokenDate(text)
                          : text;
                    setAnswer(field.id, value);
                  } catch (error) {
                    setError((error as Error).message);
                  }
                }}
              >
                <input
                  required
                  aria-label={field.label}
                  type={
                    field.type === "number"
                      ? "number"
                      : field.type === "date"
                        ? "date"
                        : "text"
                  }
                  step="any"
                  maxLength={500}
                  value={values[field.id] ?? ""}
                  onChange={(e) => setAnswer(field.id, e.target.value)}
                />
              </WorkspaceVoiceField>
            </label>
          )}
        </div>
      )}
      {error && <small className="mitra-error">{error}</small>}
      <div className="question-actions question-flow-actions">
        {step > 0 && (
          <button type="button" className="secondary" onClick={() => { setStep((current) => current - 1); setError(""); }}>
            Back
          </button>
        )}
        <button
          type="button"
          className="secondary question-skip"
          onClick={() =>
            void sendAssistant("Skip these details", {
              approval: false,
              pending_id: pending.id,
            })
          }
        >
          Skip for now
        </button>
        <button type="submit" className="question-primary">
          {step >= fields.length - 1 ? "Send answers" : "Continue"} <ArrowRight size={15} />
        </button>
      </div>
    </form>
  );
}

const MessageBubble = memo(function MessageBubble({
  message,
  liveStatus,
  canRewrite = false,
}: {
  canRewrite?: boolean;
  message: ChatMessage;
  liveStatus: string;
}) {
  return (
    <article className={`mitra-message ${message.role}`}>
      {message.role === "assistant" && (
        <div className="message-author">
          <span>
            <Leaf size={13} />
          </span>
          Kisan Mitra
        </div>
      )}
      {message.activities.length > 0 && (
        <details className="mitra-activity" open={message.status === "working"}>
          <summary>
            <span>
              {message.status === "working" ? (
                <Loader2 size={13} className="mitra-spin" />
              ) : (
                <Check size={13} />
              )}{" "}
              {message.status === "working"
                ? "Working through your request"
                : `${message.activities.length} ${message.activities.length === 1 ? "step" : "steps"}`}
            </span>
            <ChevronDown size={12} />
          </summary>
          <div>
            {message.activities.map((activity, i) => (
              <div
                className={`activity-row ${activity.status}`}
                key={activity.call_id}
              >
                <span className="activity-symbol">
                  {activity.status === "running" ? (
                    <Loader2 size={13} className="mitra-spin" />
                  ) : activity.status === "error" ? (
                    <AlertCircle size={13} />
                  ) : (
                    <Check size={13} />
                  )}
                </span>
                <div>
                  <strong>{activity.label}</strong>
                  <small>
                    {activity.status === "running"
                      ? "In progress"
                      : activity.status === "error"
                        ? activity.error
                        : activity.tool === "load_skill"
                          ? "Workflow loaded"
                          : activity.result?.artifact
                            ? "File created"
                            : activity.result?.available === false
                              ? "Data unavailable — no values assumed"
                              : activity.result?.saved
                                ? "Saved to your workspace"
                                : "Finished"}
                    {activity.elapsed_ms != null &&
                      ` · ${(activity.elapsed_ms / 1000).toFixed(1)}s`}
                  </small>
                </div>
              </div>
            ))}
          </div>
        </details>
      )}
      {message.text && (
        <div className="message-text" translate="no">
          <Markdown
            remarkPlugins={[remarkGfm]}
            disallowedElements={["img"]}
            urlTransform={(url) => (/^https?:\/\//i.test(url) ? url : "")}
            components={{
              a: ({ children, href }) => (
                <a href={href} target="_blank" rel="noopener noreferrer">
                  {children}
                </a>
              ),
            }}
          >
            {message.text}
          </Markdown>
        </div>
      )}
      {message.role === "assistant" &&
        message.text &&
        message.status !== "working" && <AnswerActions text={message.text} messageId={message.id} scope={getAssistantSessionId() || ""} onRetry={canRewrite ? () => rewriteAssistantAnswer(message.serverId || message.id) : undefined} />}
      {message.activities.map((activity) =>
        activity.status === "done" && activity.result ? (
          <FarmResult key={activity.call_id} result={activity.result} />
        ) : null,
      )}
      {message.error && (
        <div className="mitra-error">
          <AlertCircle size={14} />
          <span>{message.error}</span>
        </div>
      )}
      {message.status === "working" &&
        !message.text &&
        message.activities.length === 0 && (
          <div className="mitra-working">
            <span />
            <span />
            <span /> {liveStatus || "Getting started"}
          </div>
        )}
    </article>
  );
});
export function AssistantChat({
  active = true,
  compact = false,
  minimal = false,
  context = "assistant",
  selectedDate,
  weatherCity,
  companionAnchor,
  onCompanionVoice,
}: {
  companionAnchor?: HTMLElement | null;
  onCompanionVoice?: () => void;
  active?: boolean;
  compact?: boolean;
  minimal?: boolean;
  context?: FarmContext;
  selectedDate?: string;
  weatherCity?: string;
}) {
  const state = useAssistant();
  const latestAnswerId = [...state.messages].reverse().find(message => message.role === "assistant")?.id;
  const [startedInline, setStartedInline] = useState(false);
  const [collapsedReply, setCollapsedReply] = useState(false);
  const [input, setInput] = useLocalDraft(
    `chat:${context}:${compact ? "helper" : "main"}:${selectedDate || ""}`,
  );
  useEffect(() => {
    if (compact) return;
    const receive = (event: Event) => {
      const text = (event as CustomEvent<string>).detail;
      if (typeof text === "string") setInput(text);
    };
    window.addEventListener("mitra-voice-draft", receive);
    return () => window.removeEventListener("mitra-voice-draft", receive);
  }, [compact, setInput]);
  const [selectedSkill, setSelectedSkill] = useState<string | null>(null);
  const [skills, setSkills] = useState(false);
  const [companion, setCompanion] = useState(false);
  const [voiceStartRequest, setVoiceStartRequest] = useState(0);
  const companionTrigger = useRef<HTMLButtonElement>(null);
  const [liveVoiceActive, setLiveVoiceActive] = useState(false);
  const [voicePanelContainer, setVoicePanelContainer] = useState<HTMLDivElement | null>(null);
  const [history, setHistory] = useState(false);
  const [tab, setTab] = useState("skills");
  const [widePanel, setWidePanel] = useState(false);
  const panelTrigger = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    const media = window.matchMedia("(min-width: 1100px)");
    const update = () => setWidePanel(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  const closePanel = () => {
    setSkills(false);
    setHistory(false);
  };

  const [downloadError, setDownloadError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [draftFiles, setDraftFiles] = useState<Attachment[]>([]);
  const [localFiles, setLocalFiles] = useState<AttachmentDraft[]>([]);
  const [online, setOnline] = useState(navigator.onLine);
  const localUpload = useRef<AbortController | null>(null);
  const owner = getAssistantSessionId();
  useEffect(() => {
    let disposed = false;
    setDraftFiles([]);
    setLocalFiles([]);
    setUploadError("");
    const refresh = () => {
      setOnline(navigator.onLine);
      if (!owner || getAssistantSessionId() !== owner || !offlineEnabled()) {
        setLocalFiles([]);
        return;
      }
      void listAttachmentDrafts(owner)
        .then((files) => {
          if (!disposed && getAssistantSessionId() === owner)
            setLocalFiles(files);
        })
        .catch(() => {

        });
    };
    refresh();
    const expiryCheck = setInterval(refresh, 60000);
    for (const name of [
      "online",
      "offline",
      "skyview-offline-change",
      "skyview-attachment-drafts-change",
    ])
      window.addEventListener(name, refresh);
    return () => {
      disposed = true;
      clearInterval(expiryCheck);
      localUpload.current?.abort();
      for (const name of [
        "online",
        "offline",
        "skyview-offline-change",
        "skyview-attachment-drafts-change",
      ])
        window.removeEventListener(name, refresh);
    };
  }, [owner]);
  async function uploadLocalFile(id: string) {
    const activeOwner = getAssistantSessionId();
    if (!navigator.onLine || !activeOwner || activeOwner !== owner) {
      setUploadError(
        "Reconnect to your farm before uploading this local file.",
      );
      return;
    }
    setUploading(true);
    setUploadError("");
    const abort = new AbortController();
    localUpload.current = abort;
    try {
      const file = await readAttachmentDraft(activeOwner, id);
      if (getAssistantSessionId() !== activeOwner)
        throw new Error("Your farm session changed. Nothing was uploaded.");
      if (abort.signal.aborted)
        throw new DOMException("Upload cancelled", "AbortError");
      const attachment = await uploadAttachment(file, abort.signal);
      if (getAssistantSessionId() !== activeOwner) return;
      setDraftFiles((files) => [...files, attachment]);
      await removeAttachmentDraft(activeOwner, id);
      setLocalFiles((files) => files.filter((item) => item.id !== id));
    } catch (error) {
      if (getAssistantSessionId() === activeOwner)
        setUploadError(
          abort.signal.aborted
            ? "Upload cancelled. Your local copy remains; a file that already reached the server may have been uploaded."
            : error instanceof Error
              ? error.message
              : "Upload failed. Your local copy remains on this device.",
        );
    } finally {
      if (localUpload.current === abort) localUpload.current = null;
      setUploading(false);
    }
  }
  const fileInput = useRef<HTMLInputElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const atBottom = useRef(true);
  const filesLibrary = useRef<HTMLDetailsElement>(null);
  const planLibrary = useRef<HTMLDetailsElement>(null);
  const latestUserId = [...state.messages]
    .reverse()
    .find((message) => message.role === "user")?.id;
  useEffect(() => {
    if (filesLibrary.current) filesLibrary.current.open = false;
    if (planLibrary.current) planLibrary.current.open = false;
  }, [latestUserId]);
  useEffect(() => {
    if (scrollRef.current) {
      if (state.messages.length === 0) scrollRef.current.scrollTop = 0;
      else if (atBottom.current)
        scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }

    const frame = requestAnimationFrame(() => {
      if (scrollRef.current && atBottom.current && state.messages.length)
        scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    });
    return () => cancelAnimationFrame(frame);
  }, [state.messages, state.pending]);
  const send = (text: string) => {
    const value =
      text.trim() ||
      (draftFiles.length
        ? `Please review the uploaded file ${draftFiles.map((f) => f.name).join(", ")}.`
        : "");
    if (!value || state.running || state.pending || uploading) return;
    setStartedInline(true);
    setCollapsedReply(false);
    setInput("");
    setDraftFiles([]);
    atBottom.current = true;
    return sendAssistant(value, {
      attachment_ids: draftFiles.map((file) => file.id),
      workspace_view: context,
      ...(context === "weather" && weatherCity ? { weather_city: weatherCity } : {}),
      ...(context === "calendar" && selectedDate
        ? { selected_date: selectedDate }
        : {}),
    });
  };
  const companionButton = (
    <button
      ref={companionTrigger}
      className="saathi-trigger"
      aria-label="Your farm companion"
      aria-expanded={companion}
      aria-controls="saathi-companion"
      onClick={() => {
        closePanel();
        setCompanion(value => !value);
      }}
    >
      <CompanionAvatar small /><span>Saathi</span>
    </button>
  );
  return (
    <div
      className={`mitra-chat ${!compact && (skills || history) ? "panel-open" : ""} ${compact ? "compact" : ""} ${minimal ? "mitra-inline-chat" : ""}`}
    >
      <div className="mitra-chat-tools" hidden={minimal}>
        <button
          onClick={(event) => {
            panelTrigger.current = event.currentTarget;
            setCompanion(false);
            setHistory(false);
            setSkills((v) => !v);
          }}
          aria-expanded={skills}
        >
          <Wrench size={14} /> Skills & tools{" "}
          <span>{state.catalog.skills.length}</span>
        </button>
        <button
          aria-label="Previous conversations"
          title="Previous conversations"
          disabled={state.running}
          aria-expanded={history}
          onClick={(event) => {
            panelTrigger.current = event.currentTarget;
            setCompanion(false);
            setSkills(false);
            setHistory((v) => !v);
          }}
        >
          <History size={15} />
        </button>
        {!compact && !minimal && (companionAnchor ? createPortal(companionButton, companionAnchor) : companionButton)}
        <button
          disabled={state.running}
          onClick={() => void newConversation()}
          title="New conversation"
          aria-label="New conversation"
        >
          <Plus size={16} />
        </button>
      </div>
      {!compact && !minimal && createPortal(<CompanionPanel open={companion} onClose={() => { setCompanion(false); companionTrigger.current?.focus(); }} onVoice={() => { onCompanionVoice?.(); void unlockSpeechAudio().catch(() => {}); setCompanion(false); setVoiceStartRequest(value => value + 1); }}/>, document.body)}
      {minimal && startedInline && !state.running && !state.pending && (
        <button
          className="mitra-inline-collapse"
          onClick={() => setCollapsedReply((v) => !v)}
        >
          {collapsedReply ? "Show last reply" : "Hide reply"}
          <ChevronDown size={12} />
        </button>
      )}
      <div
        className="mitra-messages"
        ref={scrollRef}
        onScroll={(e) => {
          const el = e.currentTarget;
          atBottom.current =
            el.scrollHeight - el.scrollTop - el.clientHeight < 90;
        }}
        role="log"
        aria-label="Conversation"
      >
        {!minimal && state.messages.length === 0 && (
          <div className="mitra-welcome">
            <div className="mitra-orb">
              <Leaf size={compact ? 25 : 32} />
            </div>
            <span className="mitra-eyebrow">YOUR FARM COMPANION</span>
            <h1>
              {compact ? (
                "A little help, right here."
              ) : (
                <>
                  Let’s get your
                  <br />
                  farm work done.
                </>
              )}
            </h1>
            <p>Ask a question. Make a plan. Leave with something useful.</p>
            <div className="mitra-prompts">
              {suggestions[context].map(([label, prompt]) => (
                <button
                  key={label}
                  disabled={!state.ready}
                  onClick={() => send(prompt)}
                >
                  <span>{label}</span>
                  <ArrowUp size={14} />
                </button>
              ))}
            </div>
          </div>
        )}
        {(minimal
          ? startedInline && !collapsedReply
            ? state.messages.slice(-2)
            : []
          : state.messages
        ).map((message) => (
          <MessageBubble
            key={message.id}
            message={message}
            canRewrite={!state.running && !state.pending && message.role === "assistant" && message.status === "completed" && message.id === latestAnswerId}
            liveStatus={message.status === "working" ? state.status : ""}
          />
        ))}
        {state.pending && !state.running && (
          <FarmerQuestion key={state.pending.id} pending={state.pending} />
        )}
        {!minimal && state.artifacts.length > 0 && (
          <details
            className="mitra-artifacts mitra-saved-library"
            ref={filesLibrary}
          >
            <summary
              aria-label={`Your files, ${state.artifacts.length} saved files`}
            >
              <FileText size={14} />
              <span>Your files</span>
              <strong>{state.artifacts.length}</strong>
              <small>Reports & sheets</small>
              <ChevronDown size={14} />
            </summary>
            {state.artifacts.map((file) => (
              <button
                key={file.file_id}
                onClick={() => {
                  setDownloadError("");
                  void downloadArtifact(file).catch((e) =>
                    setDownloadError(e.message),
                  );
                }}
              >
                <span className="artifact-icon">
                  <FileText size={18} />
                </span>
                <span>
                  <strong>{file.title}</strong>
                  <small>
                    {file.format.toUpperCase()} ·{" "}
                    {Math.max(1, Math.round(file.size / 1024))} KB
                  </small>
                </span>
                <Download size={15} />
              </button>
            ))}
            {downloadError && <p className="mitra-error">{downloadError}</p>}
          </details>
        )}
        {!minimal && state.tasks.length > 0 && (
          <details
            className="mitra-task-list mitra-saved-library"
            ref={planLibrary}
          >
            <summary aria-label={`Your farm plan, ${state.tasks.length} tasks`}>
              <Check size={14} />
              <span>Your farm plan</span>
              <strong>{state.tasks.length}</strong>
              <small>
                {state.tasks.filter((task) => !task.completed).length} open
              </small>
              <ChevronDown size={14} />
            </summary>
            {state.tasks.map((task) => (
              <article key={task.id}>
                <span className={task.completed ? "task-done" : ""}>
                  <Check size={14} />
                </span>
                <div>
                  <strong>{task.title}</strong>
                  <small>
                    {task.completed ? "Completed" : `Due ${task.due_date}`}
                  </small>
                </div>
                {!task.completed && (
                  <button
                    disabled={state.running || !!state.pending}
                    onClick={() =>
                      send(
                        `Mark my saved task named ${task.title} as completed. Ask me to review it first.`,
                      )
                    }
                  >
                    Done
                  </button>
                )}
              </article>
            ))}
          </details>
        )}
        {state.error && (
          <div className="mitra-error">
            <AlertCircle size={16} />
            <span>{state.error}</span>
            <button onClick={() => void initializeAssistant()}>Retry</button>
          </div>
        )}
      </div>
      {uploadError && (
        <p className="mitra-error" role="alert">
          {uploadError}
        </p>
      )}
      {!minimal && context === "station" && state.messages.length > 0 && (
        <div className="calendar-quick-actions station-context-prompts">
          {suggestions.station.map(([label, prompt]) => (
            <button
              key={label}
              disabled={!state.ready || state.running || !!state.pending}
              onClick={() => send(prompt)}
            >
              {label}
            </button>
          ))}
        </div>
      )}
      {minimal && (
        <div className="calendar-quick-actions">
          {suggestions[context].map(([label, prompt]) => (
            <button
              key={label}
              disabled={!state.ready || state.running || !!state.pending}
              onClick={() => send(prompt)}
            >
              {label}
            </button>
          ))}
        </div>
      )}
      {!compact && !minimal && <div ref={setVoicePanelContainer} className="mitra-voice-panel-slot" />}
      <form
        className="mitra-composer"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        {draftFiles.length > 0 && (
          <div className="attachment-chips">
            {draftFiles.map((file) => (
              <span key={file.id}>
                <FileText size={12} />
                {file.name}
                <button
                  type="button"
                  onClick={() =>
                    setDraftFiles((files) =>
                      files.filter((f) => f.id !== file.id),
                    )
                  }
                  aria-label={`Remove ${file.name}`}
                >
                  <X size={11} />
                </button>
              </span>
            ))}
          </div>
        )}
        {localUpload.current && uploading && (
          <button
            type="button"
            className="local-upload-cancel"
            onClick={() => localUpload.current?.abort()}
          >
            Cancel file upload
          </button>
        )}
        {localFiles.length > 0 && (
          <div
            className="local-attachment-drafts"
            aria-label="Files kept on this device"
          >
            {localFiles.map((file) => (
              <article key={file.id}>
                <FileText size={15} />
                <div>
                  <strong>{file.name}</strong>
                  <small>
                    On this device · {(file.size / 1024).toFixed(0)} KB ·
                    expires{" "}
                    {new Date(
                      file.createdAt + 24 * 60 * 60 * 1000,
                    ).toLocaleString([], {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </small>
                  <small>Not uploaded · Upload when online</small>
                </div>
                <button
                  type="button"
                  disabled={
                    !online ||
                    uploading ||
                    state.running ||
                    !state.ready ||
                    (!!state.pending &&
                      !(
                        state.pending.kind === "question" &&
                        state.pending.arguments.fields?.some(
                          (field) => field.type === "photo",
                        )
                      ))
                  }
                  onClick={() => void uploadLocalFile(file.id)}
                >
                  Upload now
                </button>
                <button
                  type="button"
                  aria-label={`Remove local ${file.name}`}
                  disabled={uploading}
                  onClick={() => {
                    if (owner)
                      void removeAttachmentDraft(owner, file.id).catch(
                        (error) =>
                          setUploadError(
                            error instanceof Error
                              ? error.message
                              : "The local copy could not be removed.",
                          ),
                      );
                  }}
                >
                  <X size={13} />
                </button>
              </article>
            ))}
          </div>
        )}
        <input
          hidden
          ref={fileInput}
          type="file"
          accept=".pdf,.docx,.xlsx,.csv,.txt,.pptx,.jpg,.jpeg,.png,.webp"
          onChange={async (e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (!file) return;
            const activeOwner = getAssistantSessionId();
            if (!activeOwner) {
              setUploadError("Open your farm session before attaching a file.");
              return;
            }
            setUploading(true);
            setUploadError("");
            try {
              if (!navigator.onLine) {
                if (!offlineEnabled())
                  throw new Error(
                    "You are offline. Enable offline copies to keep this file on this device. Nothing was uploaded.",
                  );
                await storeAttachmentDraft(activeOwner, file);
                if (getAssistantSessionId() === activeOwner)
                  setLocalFiles(await listAttachmentDrafts(activeOwner));
              } else {
                const attachment = await uploadAttachment(file);
                if (getAssistantSessionId() === activeOwner)
                  setDraftFiles((files) => [...files, attachment]);
              }
            } catch (error) {
              if (getAssistantSessionId() === activeOwner)
                setUploadError(
                  error instanceof Error
                    ? error.message
                    : "This file could not be uploaded.",
                );
            } finally {
              setUploading(false);
            }
          }}
        />
        <textarea
          aria-label="Message Kisan Mitra"
          onFocus={() => {
            setSkills(false);
            setHistory(false);
          }}
          rows={2}
          placeholder={
            state.pending
              ? "Complete the card above to continue…"
              : minimal
                ? {
                    calendar: "Ask Mitra to update your plan…",
                    today: "A little help with today…",
                    fields: "Ask about this field or soil report…",
                    ledger: "Ask about costs, sales or your budget…",
                    followups: "Ask about your crop observations…",
                    missions: "A little help with your next step…",
                    memory: "Review or correct what Mitra remembers…",
                    crops: "Ask about your crop check…",
                    markets: "Ask about prices or selling…",
                    schemes: "Ask about support for your farm…",
                    records: "Ask about your files or costs…",
                    station: "Ask about your field readings…",
                    assistant: "Ask Mitra to help with your farm…",
                  }[context]
                : context === "station"
                  ? "Ask about your field readings…"
                  : "Ask Mitra to help with your farm…"
          }
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={!!state.pending || state.loading}
          maxLength={6000}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(input);
            }
          }}
        />
        <div className="composer-footer">
          {!compact && !minimal && <LiveConversation visible={active} startRequest={voiceStartRequest} container={voicePanelContainer}
            disabled={!active || uploading || !state.ready || !!state.pending}
            running={state.running} pending={!!state.pending}
            latest={[...state.messages].reverse().find(message => message.role === 'assistant')}
            onSend={send} onInterrupt={stopAssistant} onActive={setLiveVoiceActive} />}
          <VoiceInput
            label="Speak to Mitra"
            presentation={!compact && !minimal ? "side" : "dialog"}
            panelContainer={voicePanelContainer}
            onOpen={() => { setSkills(false); setHistory(false); setCompanion(false); }}
            disabled={
              liveVoiceActive || !active || skills || history || uploading || state.running || !!state.pending || !state.ready
            }
            onTranscript={(text) => setInput(input ? `${input} ${text}` : text)}
          />
          <button
            type="button"
            className="attachment-button"
            aria-label="Upload file"
            title={
              online
                ? "Add a crop photo, cost sheet or report (up to 5 MB)"
                : "Keep a file on this device with offline copies enabled (up to 5 MB)"
            }
            disabled={
              uploading ||
              state.running ||
              !!state.pending ||
              (!state.ready && (online || !owner))
            }
            onClick={() => fileInput.current?.click()}
          >
            {uploading ? (
              <Loader2 size={16} className="mitra-spin" />
            ) : (
              <Paperclip size={16} />
            )}
          </button>
          <span>
            <span className={`assistant-dot ${state.ready ? "ready" : ""}`} />
            {state.running
              ? state.status || "Working"
              : state.loading
                ? "Connecting"
                : state.pending
                  ? "Waiting for your input"
                  : "Skills, tools & a little care"}
          </span>
          {state.running ? (
            <button
              type="button"
              onClick={stopAssistant}
              aria-label="Stop response"
            >
              <Square size={14} />
            </button>
          ) : (
            <button
              type="submit"
              aria-label="Send message"
              disabled={
                (!input.trim() && draftFiles.length === 0) ||
                !state.ready ||
                !!state.pending ||
                uploading
              }
            >
              <ArrowUp size={17} />
            </button>
          )}
        </div>
      </form>
      <div className="mitra-footnote">
        Uses available data. Important decisions deserve a field check.
      </div>
      <Dialog.Root
        open={active && (skills || history)}
        modal={!widePanel}
        onOpenChange={(open) => {
          if (!open) closePanel();
        }}
      >
        <Dialog.Portal>
          {!widePanel && (
            <Dialog.Overlay className="mitra-side-panel-overlay" />
          )}
          <Dialog.Content
            className={`mitra-chat-side-panel ${skills ? "mitra-tools-panel" : "mitra-history-panel"}`}
            aria-describedby={undefined}
            onInteractOutside={(event) => {
              if (widePanel) event.preventDefault();
            }}
            onCloseAutoFocus={(event) => {
              event.preventDefault();
              if (active) panelTrigger.current?.focus();
            }}
          >
            <Dialog.Title className="sr-only">
              {history ? "Chat history" : "Skills and tools"}
            </Dialog.Title>
            {history && (
              <section className="mitra-skill-library">
                <header>
                  <strong>Previous conversations</strong>
                  <button
                    aria-label="Close history"
                    onClick={() => setHistory(false)}
                  >
                    <X size={15} />
                  </button>
                </header>
                <div className="recent-chat-list">
                  {state.conversations.length === 0 ? (
                    <p>Your previous chats will appear here.</p>
                  ) : (
                    state.conversations.map((chat) => (
                      <button
                        key={chat.id}
                        onClick={() => {
                          setHistory(false);
                          void restoreConversation(chat.id);
                        }}
                      >
                        <History size={14} />
                        <span>{chat.title}</span>
                      </button>
                    ))
                  )}
                </div>
              </section>
            )}
            {skills && (
              <section className="mitra-skill-library">
                <header>
                  <div>
                    <strong>Your farm toolkit</strong>
                    <small>Practical workflows, real actions</small>
                  </div>
                  <button
                    onClick={() => setSkills(false)}
                    aria-label="Close skills"
                  >
                    <X size={16} />
                  </button>
                </header>
                <div className="library-tabs">
                  <button
                    className={tab === "skills" ? "selected" : ""}
                    onClick={() => setTab("skills")}
                  >
                    Skills · {state.catalog.skills.length}
                  </button>
                  <button
                    className={tab === "tools" ? "selected" : ""}
                    onClick={() => setTab("tools")}
                  >
                    Tools · {state.catalog.tools.length}
                  </button>
                </div>
                <div className="library-list">
                  {(tab === "skills"
                    ? state.catalog.skills
                    : state.catalog.tools
                  ).map((item) => (
                    <article
                      key={item.id}
                      role="button"
                      tabIndex={0}
                      aria-expanded={selectedSkill === item.id}
                      onClick={() =>
                        setSelectedSkill(
                          selectedSkill === item.id ? null : item.id,
                        )
                      }
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setSelectedSkill(
                            selectedSkill === item.id ? null : item.id,
                          );
                        }
                      }}
                    >
                      <span>
                        <Leaf size={15} />
                      </span>
                      <div>
                        <strong>{item.name}</strong>
                        <p>{item.description}</p>
                        {selectedSkill === item.id && (
                          <div className="skill-detail">
                            <Markdown>
                              {"workflow" in item
                                ? String(item.workflow ?? item.description)
                                : `${item.description}\n\n${"approval" in item && item.approval ? "You review this action before anything is saved." : "This tool runs when needed and reports its actual result in the conversation."}`}
                            </Markdown>
                          </div>
                        )}
                      </div>
                      {"approval" in item && item.approval && (
                        <small>Review</small>
                      )}
                    </article>
                  ))}
                </div>
              </section>
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
