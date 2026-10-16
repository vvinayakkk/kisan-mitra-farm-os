import { useEffect, useRef, useState } from "react";
import { WifiOff, DownloadCloud, Paperclip } from "lucide-react";
import { offlineEnabled, setOfflineEnabled } from "@/lib/offlineStore";
import { storeAttachmentDraft } from "@/lib/attachmentDrafts";
import { getAssistantSessionId } from "@/lib/assistantClient";

export function OfflineStatus() {
  const [online, setOnline] = useState(navigator.onLine);
  const [enabled, setEnabled] = useState(offlineEnabled);
  const [shellReady, setShellReady] = useState(
    Boolean(navigator.serviceWorker?.controller),
  );
  const [message, setMessage] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (!navigator.serviceWorker) return;
    let alive = true;
    const update = () => {
      if (alive) setShellReady(Boolean(navigator.serviceWorker.controller));
    };
    navigator.serviceWorker.addEventListener("controllerchange", update);
    void navigator.serviceWorker
      .getRegistration()
      .then((registration) => {
        if (alive) setShellReady(Boolean(registration?.active));
      })
      .catch(() => {});
    return () => {
      alive = false;
      navigator.serviceWorker.removeEventListener("controllerchange", update);
    };
  }, []);
  useEffect(() => {
    const update = () => {
      setOnline(navigator.onLine);
      setEnabled(offlineEnabled());
    };
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    window.addEventListener("skyview-offline-change", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
      window.removeEventListener("skyview-offline-change", update);
    };
  }, []);
  async function keepFile(file?: File) {
    const owner = getAssistantSessionId();
    if (!file || !owner) return;
    setMessage("");
    try {
      await storeAttachmentDraft(owner, file);
      if (getAssistantSessionId() === owner)
        setMessage(
          "Kept on this device for 24 hours. Open Mitra to review and upload it when ready.",
        );
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "This file could not be kept on this device.",
      );
    }
  }
  return (
    <details className="offline-status">
      <summary>
        {online ? <DownloadCloud size={13} /> : <WifiOff size={13} />}{" "}
        {online
          ? enabled
            ? "Offline reading on"
            : "Save for offline"
          : "Offline · saved readings only"}
      </summary>
      <div>
        <p className="offline-shell-ready">
          {shellReady
            ? "App ready for offline opening."
            : "Offline opening becomes available after the saved app finishes installing in your browser."}
        </p>
        <p>
          Keep dated readings on this device for up to 24 hours. Drafts stay
          local. Reconnect and review before saving farm changes; nothing is
          sent automatically.
        </p>
        <label>
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => {
              setOfflineEnabled(e.target.checked);
              setEnabled(offlineEnabled());
              setMessage("");
            }}
          />{" "}
          Keep snapshots and local files on this device
        </label>
        {enabled && (
          <button
            type="button"
            className="offline-keep-file"
            onClick={() => fileInput.current?.click()}
          >
            <Paperclip size={13} /> Keep a photo or file locally
          </button>
        )}
        <input
          ref={fileInput}
          type="file"
          hidden
          accept="image/jpeg,image/png,image/webp,.pdf,.docx,.xlsx,.csv,.txt,.pptx"
          onChange={(event) => {
            void keepFile(event.target.files?.[0]);
            event.target.value = "";
          }}
        />
        {message && <p role="status">{message}</p>}
        <small>
          Up to 3 pending files, 5 MB each. Local files are not uploaded until
          you choose Upload now. Turn off or logout to clear saved copies. Avoid
          enabling this on shared devices.
        </small>
      </div>
    </details>
  );
}
