import { useCallback, useEffect, useState } from "react";
import { getAssistantSessionId } from "@/lib/assistantClient";
/** Local drafts are never sent until the farmer explicitly submits them. */
export function useLocalDraft(scope: string): [string, (value: string) => void, () => void] {
  const session = getAssistantSessionId();
  const key = session ? `skyview-draft-v1:${session}:${scope}` : null;
  const read = useCallback(() => { try { return key ? localStorage.getItem(key) || "" : ""; } catch { return ""; } }, [key]);
  const [draft, update] = useState(read);
  useEffect(() => { update(read()); }, [read]);
  const setDraft = useCallback((value: string) => { update(value); if (!key) return; try { if (value) localStorage.setItem(key, value.slice(0, 6000)); else localStorage.removeItem(key); } catch { /* Keep in-memory draft if storage is full. */ } }, [key]);
  return [draft, setDraft, useCallback(() => setDraft(""), [setDraft])];
}
