import { useEffect, useRef, useState } from "react";
import { ArrowUp, Check, Leaf, LoaderCircle, X } from "lucide-react";
import { WorkspaceVoiceField } from "@/components/WorkspaceVoiceField";
import {
  exchangeRequest,
  type ExchangeAssistDraft,
  type ExchangeAssistIntent,
  type ExchangeAssistResult,
} from "@/lib/exchangeClient";
import "./exchange-mitra.css";

export function ExchangeMitra({
  intent = "prepare_listing",
  listingId,
  conversationId,
  compact = false,
  onUseDraft,
  onClose,
}: {
  intent?: ExchangeAssistIntent;
  listingId?: string;
  conversationId?: string;
  compact?: boolean;
  onClose?: () => void;
  onUseDraft?: (draft: ExchangeAssistDraft) => void;
}) {
  const [message, setMessage] = useState("");
  const [result, setResult] = useState<ExchangeAssistResult | null>(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [used, setUsed] = useState(false);
  const active = useRef<AbortController | null>(null);
  const brief = useRef<string[]>([]);
  useEffect(() => {
    brief.current = [];
    setResult(null);
    setError("");
    setUsed(false);
    setMessage("");
    setBusy(false);
    return () => {
      active.current?.abort();
      active.current = null;
    };
  }, [intent, listingId, conversationId]);
  async function ask(event: React.FormEvent) {
    event.preventDefault();
    if (!message.trim() || busy) return;
    const text = message.trim();
    const combined = [...brief.current, text].join("\nFarmer follow-up: ");
    if (combined.length > 4000) {
      setError(
        "This brief is getting long. Start a new brief or shorten your reply.",
      );
      return;
    }
    active.current?.abort();
    const abort = new AbortController();
    active.current = abort;
    setBusy(true);
    setError("");
    setUsed(false);
    setResult(null);
    try {
      const response = await exchangeRequest<ExchangeAssistResult>("/assist", {
        method: "POST",
        signal: abort.signal,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          intent,
          message: combined,
          ...(listingId ? { listing_id: listingId } : {}),
          ...(conversationId ? { conversation_id: conversationId } : {}),
        }),
      });
      if (!abort.signal.aborted && active.current === abort) {
        setResult(response);
        brief.current = [...brief.current, text];
        setMessage("");
      }
    } catch (e) {
      if (!abort.signal.aborted && active.current === abort)
        setError((e as Error).message);
    } finally {
      if (active.current === abort) {
        setBusy(false);
        active.current = null;
      }
    }
  }
  const title =
    intent === "prepare_listing"
      ? "Tell Mitra what you have. Or what you need."
      : intent === "compare_matches"
        ? "Find the fit, before you connect."
        : intent === "draft_terms"
          ? "Make a fair agreement, together."
          : "A second pair of eyes on this exchange.";
  const placeholder =
    intent === "prepare_listing"
      ? "I have a sprayer for two days. I need help with my harvest…"
      : intent === "draft_terms"
        ? "Help me write terms for quantity, handover and transport…"
        : intent === "compare_matches"
          ? "Which options fit my resource and exchange wishes?"
          : "What is missing before we agree or hand over?";
  return (
    <section
      className={`exchange-mitra ${compact ? "compact" : ""}`}
      aria-label="Mitra exchange assistant"
    >
      <header>
        <span className="exchange-mitra-mark">
          <Leaf size={20} />
        </span>
        <div>
          <small>MITRA · YOUR EXCHANGE GUIDE</small>
          <h2>{title}</h2>
        </div>
        {onClose && (
          <button
            type="button"
            className="exchange-mitra-close"
            aria-label="Close exchange Mitra"
            onClick={onClose}
          >
            <X size={16} />
          </button>
        )}
      </header>
      {!compact && (
        <p className="exchange-mitra-intro">
          Turn a few words into a clear offer. Compare real resources. Keep the
          final decision yours.
        </p>
      )}
      <form onSubmit={ask}>
        <WorkspaceVoiceField
          label="Speak to exchange Mitra"
          disabled={busy}
          onTranscript={(text) =>
            setMessage((value) => (value ? `${value} ${text}` : text))
          }
        >
          <textarea
            aria-label="Ask exchange Mitra"
            rows={compact ? 2 : 2}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder={placeholder}
            maxLength={4000}
          />
        </WorkspaceVoiceField>
        {busy ? (
          <button
            type="button"
            aria-label="Cancel Mitra request"
            onClick={() => {
              active.current?.abort();
              active.current = null;
              setBusy(false);
            }}
          >
            <X size={18} />
          </button>
        ) : (
          <button aria-label="Ask Mitra" disabled={!message.trim()}>
            <ArrowUp size={19} />
          </button>
        )}
      </form>
      {busy && (
        <p className="exchange-mitra-status" role="status">
          <LoaderCircle size={13} className="exchange-mitra-spinner" /> Reading
          your exchange context…
        </p>
      )}
      {error && (
        <p role="alert" className="exchange-mitra-error">
          {error} Your resource has not been changed.
        </p>
      )}
      {result && (
        <div className="exchange-mitra-answer" aria-live="polite">
          <p>{result.answer}</p>
          {!!result.questions?.length && (
            <ul className="exchange-mitra-questions">
              {result.questions.map((question, index) => (
                <li key={index}>{question}</li>
              ))}
            </ul>
          )}
          {result.draft && (
            <div className="exchange-mitra-draft">
              <small>REVIEWABLE DRAFT · NOT SAVED</small>
              {result.draft.kind === "listing" && result.draft.fields && (
                <dl>
                  {Object.entries(result.draft.fields)
                    .filter(([, value]) => value != null && value !== "")
                    .map(([key, value]) => (
                      <div key={key}>
                        <dt>{key.replace(/_/g, " ")}</dt>
                        <dd>{String(value)}</dd>
                      </div>
                    ))}
                </dl>
              )}
              {result.draft.kind === "terms" && <p>{result.draft.text}</p>}
              {onUseDraft && (
                <button
                  type="button"
                  disabled={used}
                  onClick={() => {
                    if (result.draft) {
                      onUseDraft(result.draft);
                      setUsed(true);
                    }
                  }}
                >
                  {used ? (
                    <>
                      <Check size={14} /> Added to review
                    </>
                  ) : (
                    <>
                      Review this draft <ArrowUp size={14} />
                    </>
                  )}
                </button>
              )}
            </div>
          )}
        </div>
      )}
      {!!brief.current.length && (
        <button
          type="button"
          className="exchange-mitra-reset"
          disabled={busy}
          onClick={() => {
            brief.current = [];
            setResult(null);
            setUsed(false);
            setError("");
          }}
        >
          Start a new brief
        </button>
      )}
      <footer>
        AI suggestions. Nothing is published, sent or agreed without your
        review.
      </footer>
    </section>
  );
}
