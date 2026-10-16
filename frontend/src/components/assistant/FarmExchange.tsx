import { PreparedBySaathi } from "./PreparedBySaathi";
import { localPresentation } from "@/lib/localPresentation";
import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  ArrowLeftRight,
  Check,
  MapPin,
  MessageCircle,
  Plus,
  Search,
  Send,
  Sprout,
  Truck,
  Users,
  Wrench,
  X,
} from "lucide-react";
import * as Dialog from "@radix-ui/react-dialog";
import { WorkspaceVoiceField } from "@/components/WorkspaceVoiceField";
import { parseSpokenNumber } from "@/lib/voiceNumbers";
import {
  exchangeRequest,
  exchangeWrite,
  type ExchangeListing,
  type ExchangeThread,
  type ExchangeMessage,
  type ExchangeEvent,
  type ExchangeAssistDraft,
} from "@/lib/exchangeClient";
import "./farm-exchange.css";
import { ExportMenu } from "./ExportMenu";
import { ExchangeMitra } from "./ExchangeMitra";
function retryKey(
  ref: { current: { signature: string; key: string } | null },
  signature: string,
) {
  if (ref.current?.signature !== signature)
    ref.current = { signature, key: crypto.randomUUID() };
  return ref.current.key;
}
const categories = [
  { id: "equipment", label: "Equipment", icon: Wrench },
  { id: "labour", label: "Helping hands", icon: Users },
  { id: "transport", label: "Transport", icon: Truck },
  { id: "produce", label: "Harvest", icon: Sprout },
];
const statusLabel: Record<string, string> = {
  open: "Connected",
  negotiating: "Discussing terms",
  agreed: "Both agreed",
  handover: "Handover confirmed",
  completed: "Exchange complete",
  cancelled: "Closed",
  disputed: "Needs resolving",
};
function time(value: string) {
  return new Date(value).toLocaleTimeString("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
  });
}
function Field({
  label,
  value,
  onChange,
  required = false,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  required?: boolean;
  type?: string;
}) {
  const [error, setError] = useState("");
  return (
    <label className="exchange-field">
      {label}
      <WorkspaceVoiceField
        label={`Speak ${label.toLowerCase()}`}
        onTranscript={(text) => {
          try {
            onChange(
              type === "number"
                ? String(parseSpokenNumber(text, { min: 0 }))
                : text,
            );
            setError("");
          } catch (e) {
            setError((e as Error).message);
          }
        }}
      >
        <input
          aria-label={label}
          type={type}
          step={type === "number" ? "any" : undefined}
          min={type === "number" ? "0.000001" : undefined}
          required={required}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      </WorkspaceVoiceField>
      {error && <small role="alert">{error}</small>}
    </label>
  );
}
export function FarmExchange({ initialListingId }: { initialListingId?: string } = {}) {
  const [focusedListing, setFocusedListing] = useState(initialListingId || "");
  const [listings, setListings] = useState<ExchangeListing[]>([]),
    [threads, setThreads] = useState<ExchangeThread[]>([]),
    [selected, setSelected] = useState(""),
    [thread, setThread] = useState<ExchangeThread | null>(null),
    [messages, setMessages] = useState<ExchangeMessage[]>([]),
    [timeline, setTimeline] = useState<ExchangeEvent[]>([]);
  const [mode, setMode] = useState<"discover" | "inbox">("discover"),
    [matchFor, setMatchFor] = useState(""),
    [mine, setMine] = useState(false),
    [category, setCategory] = useState(""),
    [search, setSearch] = useState(""),
    [draft, setDraft] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true),
    [editor, setEditor] = useState(false),
    [editing, setEditing] = useState<ExchangeListing | null>(null),
    [listingDraft, setListingDraft] = useState<
      ExchangeAssistDraft["fields"] | null
    >(null),
    [review, setReview] = useState<string | null>(null),
    [terms, setTerms] = useState(""),
    [refresh, setRefresh] = useState(0),
    [journeyOpen, setJourneyOpen] = useState(false),
    [discoveryNote, setDiscoveryNote] = useState("");
  const messageAttempt = useRef<{ signature: string; key: string } | null>(
    null,
  );
  const actionAttempt = useRef<{ signature: string; key: string } | null>(null);
  const mitraDisclosure = useRef<HTMLDetailsElement>(null);
  const mitraSummary = useRef<HTMLElement>(null);
  const cursor = useRef(0),
    end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (mode !== "inbox") return;
    const abort = new AbortController();
    let fetching = false;
    const updateInbox = async () => {
      if (document.hidden || fetching) return;
      fetching = true;
      try {
        const result = await exchangeRequest<{ items: ExchangeThread[] }>(
          "/conversations",
          { signal: abort.signal },
        );
        if (!abort.signal.aborted) setThreads(result.items || []);
      } catch (error) {
        if (!abort.signal.aborted) setError((error as Error).message);
      } finally {
        fetching = false;
      }
    };
    const interval = setInterval(() => void updateInbox(), 12000);
    document.addEventListener("visibilitychange", updateInbox);
    return () => {
      abort.abort();
      clearInterval(interval);
      document.removeEventListener("visibilitychange", updateInbox);
    };
  }, [mode]);
  useEffect(() => {
    if (!journeyOpen) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") setJourneyOpen(false);
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [journeyOpen]);
  useEffect(() => {
    const abort = new AbortController();
    let alive = true;
    setLoading(true);
    setError("");
    const timer = setTimeout(() => {
      void Promise.all([
        exchangeRequest<{ items: ExchangeListing[]; note?: string }>(
          matchFor
            ? `/matches?listing_id=${encodeURIComponent(matchFor)}`
            : `/listings?${new URLSearchParams({ ...(category ? { category } : {}), ...(focusedListing && !mine ? { listing_id: focusedListing } : {}), q: search, mine: String(mine) })}`,
          { signal: abort.signal },
        ),
        exchangeRequest<{ items: ExchangeThread[] }>("/conversations", {
          signal: abort.signal,
        }),
      ])
        .then(([l, t]) => {
          if (alive) {
            setListings(l.items || []);
            setDiscoveryNote(l.note || "");
            setThreads(t.items || []);
          }
        })
        .catch((e) => {
          if (alive && e.name !== "AbortError") setError(e.message);
        })
        .finally(() => {
          if (alive) setLoading(false);
        });
    }, 180);
    return () => {
      alive = false;
      clearTimeout(timer);
      abort.abort();
    };
  }, [category, search, mine, matchFor, refresh, focusedListing]);
  useEffect(() => {
    if (!selected) {
      setThread(null);
      setMessages([]);
      return;
    }
    const abort = new AbortController();
    let alive = true,
      fetching = false;
    cursor.current = 0;
    const load = async () => {
      if (!alive || fetching || document.hidden) return;
      fetching = true;
      try {
        const d = await exchangeRequest<{
          thread: ExchangeThread;
          messages: ExchangeMessage[];
          timeline: ExchangeEvent[];
        }>(
          `/conversations/${selected}${cursor.current > 0 ? "?include_messages=false" : ""}`,
          { signal: abort.signal },
        );
        if (cursor.current > 0) {
          const incremental = await exchangeRequest<{
            items: ExchangeMessage[];
            next_cursor: number;
          }>(`/conversations/${selected}/messages?after=${cursor.current}`, {
            signal: abort.signal,
          });
          d.messages = incremental.items;
        }
        if (alive) {
          setThread(d.thread);
          setMessages((previous) => {
            const map = new Map(previous.map((m) => [m.sequence, m]));
            (d.messages || []).forEach((m) => map.set(m.sequence, m));
            return [...map.values()]
              .sort((a, b) => a.sequence - b.sequence)
              .slice(-300);
          });
          setTimeline(d.timeline || []);
          cursor.current = Math.max(
            cursor.current,
            ...(d.messages || []).map((m) => m.sequence),
          );
        }
      } catch (e) {
        if (alive && (e as Error).name !== "AbortError")
          setError((e as Error).message);
      } finally {
        fetching = false;
      }
    };
    void load();
    const timer = setInterval(() => void load(), 7000);
    document.addEventListener("visibilitychange", load);
    return () => {
      alive = false;
      abort.abort();
      clearInterval(timer);
      document.removeEventListener("visibilitychange", load);
    };
  }, [selected, refresh]);
  useEffect(() => {
    setDraft("");
    setThread(null);
    setMessages([]);
  }, [selected]);
  useEffect(() => {
    const messages = end.current?.parentElement;
    if (messages) messages.scrollTop = messages.scrollHeight;
  }, [messages.length]);
  async function connect(listing: ExchangeListing) {
    setBusy(true);
    setError("");
    try {
      const t = await exchangeWrite<ExchangeThread>("/conversations", {
        listing_id: listing.id,
        consent_to_share_display_name: true,
      });
      setSelected(t.id);
      setMode("inbox");
      setRefresh((n) => n + 1);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (!draft.trim() || !selected) return;
    setBusy(true);
    setError("");
    try {
      await exchangeWrite(`/conversations/${selected}/messages`, {
        text: draft.trim(),
        client_key: retryKey(messageAttempt, `${selected}:${draft.trim()}`),
      });
      setDraft("");
      messageAttempt.current = null;
      setRefresh((n) => n + 1);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function act() {
    if (!review || !thread) return;
    setBusy(true);
    setError("");
    try {
      await exchangeWrite(`/conversations/${thread.id}/actions`, {
        action: review,
        row_version: thread.row_version,
        client_key: retryKey(
          actionAttempt,
          `${thread.id}:${thread.row_version}:${review}:${terms.trim()}`,
        ),
        ...(["propose", "dispute"].includes(review)
          ? { terms: terms.trim() }
          : {}),
      });
      setReview(null);
      actionAttempt.current = null;
      setTerms("");
      setRefresh((n) => n + 1);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function useListingDraft(draft: ExchangeAssistDraft) {
    if (draft.kind !== "listing" || !draft.fields) return;
    setEditing(null);
    setListingDraft(draft.fields);
    setEditor(true);
  }
  const closed =
    thread && ["completed", "cancelled", "disputed"].includes(thread.status);
  return (
    <section
      className={`farm-exchange ${selected && mode === "inbox" ? "has-thread" : "is-browsing"}`}
      aria-label="Farmer exchange"
    >
      <header className="exchange-heading">
        <p className="exchange-guide-caption">Share a resource. Find a fair exchange.</p>
        <button
          className="exchange-primary"
          onClick={() => {
            setEditing(null);
            setListingDraft(null);
            setEditor(true);
          }}
        >
          <Plus size={16} /> Post an offer or need
        </button>
      </header>
      {mode === "discover" && (
        <>
          <div className="exchange-prepared"><PreparedBySaathi area="exchange"/></div>
          <ExchangeMitra
            intent={matchFor ? "compare_matches" : "prepare_listing"}
            listingId={matchFor || undefined}
            onUseDraft={useListingDraft}
          />
          <ol className="exchange-route" aria-label="Exchange journey">
            {[
              "Tell Mitra",
              "Find a fit",
              "Talk it through",
              "Agree together",
              "Confirm handover",
            ].map((label, index) => (
              <li key={label}>
                <span>{index + 1}</span>
                {label}
                {index < 4 && <ArrowRight size={13} />}
              </li>
            ))}
          </ol>
        </>
      )}
      <nav className="exchange-switch" aria-label="Exchange views">
        <button
          aria-pressed={mode === "discover"}
          onClick={() => {
            setMode("discover");
            setSelected("");
          }}
        >
          Explore resources <ArrowLeftRight size={15} />
        </button>
        <button
          aria-pressed={mode === "inbox"}
          onClick={() => setMode("inbox")}
        >
          Conversations <MessageCircle size={15} />
          <span>{threads.length}</span>
        </button>
        <ExportMenu
          filename={
            mode === "inbox"
              ? selected
                ? "exchange-messages"
                : "my-exchange-inbox"
              : mine
                ? "my-farm-resources"
                : "published-farm-resources"
          }
          rows={mode === "inbox" ? (selected ? messages : threads) : listings}
          note={
            mode === "inbox" && thread
              ? `Exchange: ${thread.listing_title}. Recorded status: ${thread.status}. Terms: ${thread.proposal?.terms || "Not agreed"}. Participant-reported progress, not verified delivery.`
              : "Only the currently loaded records are included."
          }
        />
        <small>Private coordination · no external messages</small>
      </nav>
      {error && (
        <p className="exchange-error" role="alert">
          {error}
          <button onClick={() => setRefresh((n) => n + 1)}>Retry</button>
        </p>
      )}
      <div className="exchange-body">
        <aside
          className={`exchange-rail ${mode === "discover" ? "discover" : ""}`}
        >
          {mode === "discover" ? (
            <>
              <div className="exchange-search">
                <Search size={16} />
                <WorkspaceVoiceField
                  label="Speak resource search"
                  onTranscript={setSearch}
                >
                  <input
                    aria-label="Search resources"
                    placeholder="What could help your farm?"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </WorkspaceVoiceField>
              </div>
              <div className="exchange-categories">
                {matchFor && (
                  <button onClick={() => setMatchFor("")}>Clear matches</button>
                )}
                <button
                  aria-pressed={mine}
                  onClick={() => {
                    setMatchFor("");
                    setMine((v) => !v);
                  }}
                >
                  {mine ? "Showing my resources" : "Manage my resources"}
                </button>
                <button
                  aria-pressed={!category}
                  onClick={() => setCategory("")}
                >
                  Everything
                </button>
                {categories.map((c) => (
                  <button
                    key={c.id}
                    aria-pressed={category === c.id}
                    onClick={() => setCategory(c.id)}
                  >
                    <c.icon size={15} />
                    {c.label}
                  </button>
                ))}
              </div>
              <p className="exchange-rail-note">
                A real conversation, a clear agreement, a handover both people
                confirm.
                <br />
                <br />
                Matches use resource details and district, not live road
                distance.
              </p>
            </>
          ) : (
            <>
              <h2>Your conversations</h2>
              {threads.length ? (
                threads.map((t) => (
                  <button
                    className={`exchange-thread-link ${selected === t.id ? "selected" : ""}`}
                    key={t.id}
                    onClick={() => {
                      setSelected(t.id);
                      setJourneyOpen(false);
                    }}
                  >
                    <span className="exchange-avatar">
                      {t.listing_title?.slice(0, 1) || "F"}
                    </span>
                    <span>
                      <strong>{t.listing_title}</strong>
                      <small>{statusLabel[t.status] || t.status}</small>
                    </span>
                    <ArrowRight size={14} />
                  </button>
                ))
              ) : (
                <div className="exchange-empty">
                  <MessageCircle size={30} />
                  <p>A useful conversation starts with a resource.</p>
                  <button onClick={() => setMode("discover")}>
                    Explore resources
                  </button>
                </div>
              )}
            </>
          )}
        </aside>
        {mode === "discover" ? (
          <main className="exchange-stream">
            <header>
              <h2>
                {matchFor
                  ? "Resources that could fit"
                  : mine
                    ? "Your offers & needs"
                    : "The resource trail"}
              </h2>
              <small>
                {loading
                  ? "Looking for resources…"
                  : `${listings.length} resources shown`}
              </small>
            </header>
            {focusedListing && !mine && <button className="exchange-primary" onClick={() => setFocusedListing("")}>Show all resources</button>}
            {!loading && !listings.length && (
              <div className="exchange-empty">
                <Sprout size={40} />
                <h3>
                  {matchFor
                    ? "No available match yet."
                    : mine
                      ? "Your resources belong here."
                      : search || category
                        ? "No resources fit this search yet."
                        : "Be the first to share something useful."}
                </h3>
                <p>
                  {discoveryNote ||
                    (matchFor
                      ? "Matching checks the named resource and stated exchange wishes. Try another available resource or return to explore."
                      : mine
                        ? "Publish an offer or a need. You can edit its details or withdraw it here."
                        : "Post an available machine, a harvest, a transport need or a skill. Other members can connect here.")}
                </p>
                <button
                  className="exchange-primary"
                  onClick={() => {
                    setEditing(null);
                    setListingDraft(null);
                    setEditor(true);
                  }}
                >
                  Post a resource
                </button>
              </div>
            )}
            {listings.map((l) => {
              const Icon =
                categories.find((c) => c.id === l.category)?.icon || Sprout;
              return (
                <article className="exchange-resource" key={l.id}>
                  <div className="exchange-resource-line">
                    <span className="exchange-resource-icon">
                      <Icon size={21} />
                    </span>
                    <div>
                      <small>
                        {l.kind === "request"
                          ? "LOOKING FOR"
                          : "AVAILABLE TO SHARE"}{" "}
                        · {l.category}
                      </small>
                      <h3>{l.title}</h3>
                      <p>{l.description}</p>
                      <div className="exchange-resource-meta">
                        <span>
                          <MapPin size={12} />
                          {[l.district, l.state].filter(Boolean).join(", ")}
                        </span>
                        <span>
                          {l.quantity} {l.unit}
                        </span>
                        {l.available_on && <span>From {l.available_on}</span>}
                      </div>
                      {l.exchange_for && (
                        <p className="exchange-barter">
                          <ArrowLeftRight size={14} /> In exchange:{" "}
                          {l.exchange_for}
                        </p>
                      )}
                      <small>
                        {!localPresentation && (l.data_origin === "synthetic" || l.source === "demo")
                          ? `Sample · ${l.owner_name || l.display_name || "Member listing"}`
                          : l.owner_name || l.display_name || "Member listing"}
                        {l.match_reasons?.length
                          ? ` · ${l.match_reasons.join(" · ")}`
                          : l.match_reason && ` · ${l.match_reason}`}
                      </small>
                    </div>
                  </div>
                  <div className="exchange-connect">
                    {!mine && (
                      <small>
                        Connecting shares your name with this member.
                      </small>
                    )}
                    <button
                      disabled={busy}
                      onClick={() => {
                        if (mine) {
                          setEditing(l);
                          setListingDraft(null);
                          setEditor(true);
                        } else void connect(l);
                      }}
                    >
                      {mine ? (
                        "Edit or withdraw"
                      ) : (
                        <>
                          Discuss exchange <ArrowRight size={15} />
                        </>
                      )}
                    </button>
                    {mine && l.status === "published" && (
                      <button
                        onClick={() => {
                          setMatchFor(l.id);
                          setMine(false);
                        }}
                      >
                        Find suitable matches
                      </button>
                    )}
                  </div>
                </article>
              );
            })}
          </main>
        ) : (
          <main className="exchange-conversation">
            {thread ? (
              <>
                <header>
                  <button
                    className="exchange-mobile-back"
                    aria-label="Back to conversations"
                    onClick={() => setSelected("")}
                  >
                    <ArrowLeft size={19} />
                  </button>
                  <div>
                    <h2>{thread.listing_title}</h2>
                    <small>
                      {thread.participants
                        .map((p) => p.display_name)
                        .join(" & ")}{" "}
                      · {statusLabel[thread.status] || thread.status}
                    </small>
                  </div>
                  <details
                    ref={mitraDisclosure}
                    className="exchange-conversation-mitra"
                  >
                    <summary ref={mitraSummary}>
                      <Sprout size={14} /> Ask Mitra
                    </summary>
                    <ExchangeMitra
                      compact
                      intent="review_exchange"
                      conversationId={thread.id}
                      onClose={() => {
                        if (mitraDisclosure.current)
                          mitraDisclosure.current.open = false;
                        mitraSummary.current?.focus();
                      }}
                    />
                  </details>
                  <button
                    className="exchange-journey-toggle"
                    onClick={() => setJourneyOpen((v) => !v)}
                  >
                    Exchange trail
                  </button>
                </header>
                <div className="exchange-message-list">
                  <p className="exchange-chat-note">
                    Keep the agreement here. Both people confirm their own
                    handover.
                  </p>
                  {messages.map((m) => (
                    <div
                      key={m.sequence}
                      className={`exchange-message ${m.is_mine || m.sender_id === thread.my_farmer_id ? "mine" : ""}`}
                    >
                      <small>
                        {m.display_name ||
                          thread.participants.find(
                            (p) => p.farmer_id === m.sender_id,
                          )?.display_name ||
                          "Member"}
                      </small>
                      <p>{m.text}</p>
                      <time>{time(m.created_at)}</time>
                    </div>
                  ))}
                  {!messages.length && (
                    <div className="exchange-empty">
                      <MessageCircle size={28} />
                      <p>
                        Ask about availability, condition and a fair exchange.
                      </p>
                    </div>
                  )}
                  <div ref={end} />
                </div>
                {!closed && (
                  <form className="exchange-compose" onSubmit={send}>
                    <WorkspaceVoiceField
                      label="Speak your message"
                      disabled={busy}
                      onTranscript={(text) =>
                        setDraft((v) => (v ? `${v} ${text}` : text))
                      }
                    >
                      <textarea
                        aria-label="Message farmer"
                        placeholder="Message this farmer…"
                        value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                        maxLength={4000}
                      />
                    </WorkspaceVoiceField>
                    <button
                      aria-label="Send message"
                      className="exchange-primary"
                      disabled={busy || !draft.trim()}
                    >
                      <Send size={18} />
                    </button>
                  </form>
                )}
              </>
            ) : (
              <div className="exchange-empty">
                <MessageCircle size={42} />
                <h3>Every connection starts a new possibility.</h3>
                <p>
                  Choose a conversation, or find someone who has what your farm
                  needs.
                </p>
                <button
                  onClick={() => {
                    setMode("discover");
                    setSelected("");
                  }}
                >
                  Find a resource <ArrowRight size={15} />
                </button>
              </div>
            )}
          </main>
        )}
        {thread && mode === "inbox" && (
          <aside className={`exchange-journey ${journeyOpen ? "is-open" : ""}`}>
            <header>
              <small>YOUR EXCHANGE TRAIL</small>
              <button
                aria-label="Close exchange trail"
                onClick={() => setJourneyOpen(false)}
              >
                <X size={16} />
              </button>
            </header>
            <h2>
              From hello
              <br />
              to handover.
            </h2>
            <ol>
              {[
                "Connected",
                "Terms discussed",
                "Both agreed",
                "Handover",
                "Complete",
              ].map((label, i) => {
                const index = [
                  "open",
                  "negotiating",
                  "agreed",
                  "handover",
                  "completed",
                ].indexOf(thread.status);
                return (
                  <li key={label} className={i <= index ? "reached" : ""}>
                    <span>{i < index ? <Check size={12} /> : i + 1}</span>
                    <div>
                      <strong>{label}</strong>
                      {i === 2 && <small>Agreement needs both people</small>}
                      {i === 3 && (
                        <small>Each confirms their own handover</small>
                      )}
                    </div>
                  </li>
                );
              })}
            </ol>
            {!closed && (
              <ExchangeMitra
                compact
                intent={
                  ["open", "negotiating"].includes(thread.status)
                    ? "draft_terms"
                    : "review_exchange"
                }
                conversationId={thread.id}
                onUseDraft={(draft) => {
                  if (
                    ["open", "negotiating"].includes(thread.status) &&
                    draft.kind === "terms" &&
                    draft.text
                  ) {
                    setTerms(draft.text);
                    setReview("propose");
                  }
                }}
              />
            )}
            {thread.proposal && (
              <div className="exchange-agreement">
                <small>LATEST PROPOSED TERMS</small>
                <p>{thread.proposal.terms}</p>
              </div>
            )}
            {!closed && (
              <div className="exchange-actions">
                {["open", "negotiating"].includes(thread.status) && (
                  <button
                    onClick={() => {
                      setReview("propose");
                      setTerms(thread.proposal?.terms || "");
                    }}
                  >
                    Propose terms
                  </button>
                )}
                {thread.status === "negotiating" && !thread.can_accept && (
                  <small className="exchange-footnote">
                    Waiting for the other farmer to review your terms.
                  </small>
                )}
                {thread.status === "negotiating" && thread.can_accept && (
                  <button
                    className="exchange-primary"
                    onClick={() => setReview("accept")}
                  >
                    Review & agree
                  </button>
                )}
                {["agreed", "handover"].includes(thread.status) && (
                  <>
                    <button
                      disabled={thread.handovers.includes(
                        thread.my_farmer_id || "",
                      )}
                      onClick={() => setReview("handover")}
                    >
                      {thread.handovers.includes(thread.my_farmer_id || "")
                        ? "Your handover confirmed"
                        : "Confirm my handover"}
                    </button>
                    <button
                      disabled={
                        thread.handovers.length < 2 ||
                        thread.completions.includes(thread.my_farmer_id || "")
                      }
                      onClick={() => setReview("complete")}
                    >
                      {thread.handovers.length < 2
                        ? "Waiting for both handovers"
                        : thread.completions.includes(thread.my_farmer_id || "")
                          ? "Waiting for other farmer"
                          : "Confirm completion"}
                    </button>
                  </>
                )}
                <button
                  className="exchange-quiet"
                  onClick={() => {
                    setTerms("");
                    setReview(
                      ["agreed", "handover"].includes(thread.status)
                        ? "dispute"
                        : "cancel",
                    );
                  }}
                >
                  {["agreed", "handover"].includes(thread.status)
                    ? "Raise a problem"
                    : "Close conversation"}
                </button>
              </div>
            )}
            <details>
              <summary>Activity record</summary>
              {timeline.map((e, i) => (
                <p key={e.id || i}>
                  <strong>
                    {(e.action || e.event_type || "Update").replace(/_/g, " ")}
                  </strong>
                  {e.result?.action_note && (
                    <small>{e.result.action_note}</small>
                  )}
                  <small>
                    {new Date(e.created_at).toLocaleString("en-IN")}
                  </small>
                </p>
              ))}
            </details>
            <p className="exchange-footnote">
              Transport is arranged between you. No GPS tracking, payment or
              road route is implied.
            </p>
          </aside>
        )}
      </div>
      {editor && (
        <ListingEditor
          initial={editing}
          suggested={listingDraft}
          onClose={() => {
            setEditor(false);
            setListingDraft(null);
          }}
          onSaved={() => {
            setEditor(false);
            setListingDraft(null);
            setMine(true);
            setMatchFor("");
            setMode("discover");
            setSearch("");
            setCategory("");
            setRefresh((n) => n + 1);
          }}
        />
      )}
      <Dialog.Root
        open={!!review}
        onOpenChange={(open) => {
          if (!open && !busy) setReview(null);
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="exchange-overlay" />
          <Dialog.Content className="exchange-modal">
            <header>
              <Dialog.Title>
                {review === "propose"
                  ? "Make the agreement clear"
                  : "Review this step"}
              </Dialog.Title>
              <button
                aria-label="Close review"
                disabled={busy}
                onClick={() => setReview(null)}
              >
                <X size={18} />
              </button>
            </header>
            <Dialog.Description className="exchange-dialog-description">
              {review === "propose"
                ? "Include what each person gives, quantity, condition, day, meeting district and who arranges transport or pays its cost."
                : review === "accept"
                  ? "Agree to the proposed terms below. Only the other participant can accept a proposal."
                  : review === "handover"
                    ? "Confirm only what you personally handed over or received. The other person must also confirm."
                    : review === "complete"
                      ? "Confirm your part is complete. This exchange closes when both people confirm."
                      : review === "dispute"
                        ? "Mark this exchange as needing resolution. This records the issue; it does not contact an external mediator."
                        : "Close this conversation before an agreement is made."}
            </Dialog.Description>
            {["propose", "dispute"].includes(review || "") ? (
              <WorkspaceVoiceField
                label="Speak exchange terms"
                onTranscript={setTerms}
              >
                <textarea
                  aria-label="Exchange terms"
                  value={terms}
                  onChange={(e) => setTerms(e.target.value)}
                  maxLength={4000}
                />
              </WorkspaceVoiceField>
            ) : (
              thread?.proposal && (
                <blockquote>{thread.proposal.terms}</blockquote>
              )
            )}
            {error && (
              <p role="alert" className="exchange-error">
                {error}
              </p>
            )}
            <footer>
              <button disabled={busy} onClick={() => setReview(null)}>
                Go back
              </button>
              <button
                className="exchange-primary"
                disabled={
                  busy ||
                  (["propose", "dispute"].includes(review || "") &&
                    terms.trim().length < 2)
                }
                onClick={() => void act()}
              >
                {busy ? "Saving…" : "Confirm this step"}
              </button>
            </footer>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </section>
  );
}
function ListingEditor({
  initial,
  suggested,
  onClose,
  onSaved,
}: {
  initial: ExchangeListing | null;
  suggested?: ExchangeAssistDraft["fields"] | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState({
      title: initial?.title || suggested?.title || "",
      category: initial?.category || suggested?.category || "equipment",
      kind: initial?.kind || suggested?.kind || "offer",
      description: initial?.description || suggested?.description || "",
      quantity: String(initial?.quantity ?? suggested?.quantity ?? ""),
      unit: initial?.unit || suggested?.unit || "item",
      state: initial?.state || suggested?.state || "",
      district: initial?.district || suggested?.district || "",
      exchange_for: initial?.exchange_for || suggested?.exchange_for || "",
      available_on: initial?.available_on || suggested?.available_on || "",
      status: initial?.status || "published",
    }),
    [consent, setConsent] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const field = (key: keyof typeof form, value: string) =>
    setForm((v) => ({ ...v, [key]: value }));
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await exchangeWrite(
        `/listings${initial ? `/${initial.id}` : ""}`,
        {
          ...form,
          available_on: form.available_on || null,
          quantity: Number(form.quantity),
          consent_to_publish: true,
          ...(initial ? { row_version: initial.row_version } : {}),
        },
        initial ? "PATCH" : "POST",
      );
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open && !busy) onClose();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="exchange-overlay" />
        <Dialog.Content className="exchange-modal">
          <header>
            <Dialog.Title>Something useful to share.</Dialog.Title>
            <button
              aria-label="Close resource editor"
              disabled={busy}
              onClick={onClose}
            >
              <X size={18} />
            </button>
          </header>
          <Dialog.Description className="exchange-dialog-description">
            Publish an offer or a need. Your display name and district will be
            visible to members.
          </Dialog.Description>
          <details className="exchange-editor-mitra">
            <summary>
              <Sprout size={14} /> Help me describe this resource
            </summary>
            <ExchangeMitra
              compact
              intent="prepare_listing"
              listingId={initial?.id}
              onUseDraft={(draft) => {
                if (draft.kind === "listing" && draft.fields) {
                  const values = draft.fields;
                  setForm((current) => ({
                    ...current,
                    ...Object.fromEntries(
                      Object.entries(values)
                        .filter(([, value]) => value != null)
                        .map(([key, value]) => [key, String(value)]),
                    ),
                  }));
                }
              }}
            />
          </details>
          <form onSubmit={save}>
            <div className="exchange-editor-grid">
              <label className="exchange-field">
                I want to
                <select
                  value={form.kind}
                  onChange={(e) => field("kind", e.target.value)}
                >
                  <option value="offer">Offer something</option>
                  <option value="request">Find something</option>
                </select>
              </label>
              <label className="exchange-field">
                Resource
                <select
                  value={form.category}
                  onChange={(e) => field("category", e.target.value)}
                >
                  {categories.map((c) => (
                    <option value={c.id} key={c.id}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </label>
              <Field
                label="Resource title"
                required
                value={form.title}
                onChange={(v) => field("title", v)}
              />
              <Field
                label="Details and condition"
                required
                value={form.description}
                onChange={(v) => field("description", v)}
              />
              <Field
                label="Quantity"
                type="number"
                required
                value={form.quantity}
                onChange={(v) => field("quantity", v)}
              />
              <Field
                label="Unit"
                required
                value={form.unit}
                onChange={(v) => field("unit", v)}
              />
              <Field
                label="State"
                required
                value={form.state}
                onChange={(v) => field("state", v)}
              />
              <Field
                label="District"
                required
                value={form.district}
                onChange={(v) => field("district", v)}
              />
              <label className="exchange-field">
                Available from
                <input
                  type="date"
                  value={form.available_on}
                  onChange={(e) => field("available_on", e.target.value)}
                />
              </label>
              {initial && (
                <label className="exchange-field">
                  Visibility
                  <select
                    value={form.status}
                    onChange={(e) => field("status", e.target.value)}
                  >
                    <option value="published">Published</option>
                    <option value="withdrawn">Withdrawn</option>
                    <option value="draft">Draft</option>
                  </select>
                </label>
              )}
              <Field
                label="What would you accept in exchange?"
                value={form.exchange_for}
                onChange={(v) => field("exchange_for", v)}
              />
            </div>
            <label className="exchange-consent">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
              />{" "}
              Share this resource, my display name and district with members.
            </label>
            {error && (
              <p className="exchange-error" role="alert">
                {error}
              </p>
            )}
            <footer>
              <button type="button" disabled={busy} onClick={onClose}>
                Cancel
              </button>
              <button
                className="exchange-primary"
                disabled={busy || (form.status === "published" && !consent)}
              >
                {busy
                  ? "Saving…"
                  : initial
                    ? "Save resource"
                    : "Publish resource"}
              </button>
            </footer>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export default FarmExchange;
