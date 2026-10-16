import { useState } from "react";
import Markdown from "react-markdown";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import {
  Copy,
  Check,
  ThumbsUp,
  ThumbsDown,
  Share,
  RotateCw,
  MoreHorizontal,
  Download,
  Printer,
  Loader2,
} from "lucide-react";
import { SpeechPlayback } from "@/components/SpeechPlayback";
import { downloadText } from "@/lib/farmExports";
import "./answer-actions.css";

export function AnswerActions({
  text,
  messageId,
  scope,
  onRetry,
}: {
  text: string;
  messageId: string;
  scope: string;
  onRetry?: () => Promise<string>;
}) {
  const [notice, setNotice] = useState("");
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [alternative, setAlternative] = useState("");
  const ratingKey = `mitra-answer-rating:${scope}:${messageId}`;
  const [vote, setVote] = useState<"up" | "down" | null>(() => {
    try {
      const saved = sessionStorage.getItem(ratingKey);
      return saved === "up" || saved === "down" ? saved : null;
    } catch {
      return null;
    }
  });
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setNotice("Answer copied.");
    } catch {
      setNotice("Copy is unavailable. Select the answer text to copy it.");
    }
  }
  async function share() {
    try {
      if (navigator.share) {
        await navigator.share({ title: "Kisan Mitra answer", text });
        setNotice("Share sheet closed.");
      } else {
        await navigator.clipboard.writeText(text);
        setNotice("Answer copied for sharing. No public link was created.");
      }
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError"))
        setNotice("Sharing is unavailable. You can copy the answer instead.");
    }
  }
  function feedback(next: "up" | "down") {
    const chosen = vote === next ? null : next;
    try {
      if (chosen) sessionStorage.setItem(ratingKey, chosen);
      else sessionStorage.removeItem(ratingKey);
      setVote(chosen);
      setNotice(
        chosen
          ? "Rating saved in this browser session. It is not sent to Mitra."
          : "Rating removed.",
      );
    } catch {
      setNotice("This browser could not save your rating.");
    }
  }
  function download(format: "txt" | "md") {
    const exported = new Date().toISOString();
    const content =
      format === "md"
        ? `# Kisan Mitra answer\n\nExported at (UTC): ${exported}\n\nOriginal answer; citations and uncertainty labels retained.\n\n${text}\n`
        : `Kisan Mitra answer\nExported at (UTC): ${exported}\nOriginal answer; citations and uncertainty labels retained.\n\n${text}\n`;
    downloadText(
      `mitra-answer-${messageId.slice(0, 12)}.${format}`,
      content,
      format === "md"
        ? "text/markdown;charset=utf-8"
        : "text/plain;charset=utf-8",
    );
    setNotice("Answer download started.");
  }
  function print() {
    const page = window.open("", "_blank", "noopener=false");
    if (!page) {
      setNotice("Allow pop-ups to print or save this answer as PDF.");
      return;
    }
    page.opener = null;
    page.document.title = "Kisan Mitra answer";
    const style = page.document.createElement("style");
    style.textContent =
      "body{max-width:760px;margin:48px auto;padding:0 24px;font:16px/1.6 system-ui;color:#172b22}pre{font:inherit;white-space:pre-wrap;overflow-wrap:anywhere}h1{font-size:22px}@media print{body{margin:0}}";
    page.document.head.append(style);
    const heading = page.document.createElement("h1");
    heading.textContent = "Kisan Mitra";
    const answer = page.document.createElement("pre");
    answer.textContent = text;
    const context = page.document.createElement("p");
    context.textContent = `Exported at (UTC): ${new Date().toISOString()} · Original answer; citations and uncertainty retained.`;
    page.document.body.append(heading, context, answer);
    page.document.close();
    page.focus();
    page.print();
  }
  return (
    <div className="answer-action-block" key={`${scope}:${messageId}`}>
      <div className="answer-actions" role="group" aria-label="Answer actions">
        <button
          className="answer-action"
          aria-label="Copy answer"
          data-hint={copied ? "Copied" : "Copy"}
          onClick={() => void copy()}
        >
          {copied ? <Check /> : <Copy />}
        </button>
        <button
          className="answer-action"
          aria-label="Helpful answer"
          aria-pressed={vote === "up"}
          data-hint="Helpful"
          onClick={() => feedback("up")}
        >
          <ThumbsUp />
        </button>
        <button
          className="answer-action"
          aria-label="Unhelpful answer"
          aria-pressed={vote === "down"}
          data-hint="Needs improvement"
          onClick={() => feedback("down")}
        >
          <ThumbsDown />
        </button>
        <button
          className="answer-action"
          aria-label="Share answer"
          data-hint="Share"
          onClick={() => void share()}
        >
          <Share />
        </button>
        <SpeechPlayback text={text} compact />
        {onRetry && (
          <button
            className="answer-action"
            aria-label="Rewrite answer without repeating tasks"
            data-hint="Rewrite answer only"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              setNotice("Rewriting the explanation. No tasks will run again.");
              try {
                setAlternative(await onRetry());
                setNotice(
                  "Alternative explanation added for this view. Original answer kept; rewrite is not saved.",
                );
              } catch (error) {
                setNotice(
                  error instanceof Error
                    ? error.message
                    : "Rewrite unavailable. Original answer is kept.",
                );
              } finally {
                setBusy(false);
              }
            }}
          >
            {busy ? <Loader2 className="animate-spin" /> : <RotateCw />}
          </button>
        )}
        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <button
              className="answer-action"
              aria-label="More answer options"
              data-hint="More"
            >
              <MoreHorizontal />
            </button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content
              className="answer-options"
              sideOffset={8}
              align="start"
            >
              <DropdownMenu.Item onSelect={() => download("md")}>
                <Download size={15} /> Download Markdown
              </DropdownMenu.Item>
              <DropdownMenu.Item onSelect={() => download("txt")}>
                <Download size={15} /> Download text
              </DropdownMenu.Item>
              <DropdownMenu.Item onSelect={print}>
                <Printer size={15} /> Print / save as PDF
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      </div>
      {alternative && (
        <details className="answer-alternative" open>
          <summary>
            Alternative explanation <small>Not saved · original above</small>
          </summary>
          <div className="message-text">
            <Markdown
              disallowedElements={["img"]}
              urlTransform={(url) => (/^https?:\/\//i.test(url) ? url : "")}
            >
              {alternative}
            </Markdown>
          </div>
        </details>
      )}
      {notice && (
        <small className="answer-action-notice" role="status">
          {notice}
        </small>
      )}
    </div>
  );
}
