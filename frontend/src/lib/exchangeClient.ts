import { apiFetch } from "./apiClient";
export interface ExchangeListing {
  id: string;
  title: string;
  category: "equipment" | "labour" | "transport" | "produce";
  kind: "offer" | "request";
  description: string;
  quantity: number;
  unit: string;
  state: string;
  district: string;
  available_on?: string | null;
  exchange_for: string;
  status: string;
  row_version: number;
  farmer_id?: string;
  display_name?: string;
  owner_name?: string;
  is_mine?: boolean;
  source?: string;
  data_origin?: string;
  match_reason?: string;
  match_reasons?: string[];
}
export interface ExchangeThread {
  id: string;
  status: string;
  row_version: number;
  listing_title: string;
  my_role: string;
  participants: { farmer_id: string; display_name: string }[];
  proposal?: { terms: string; proposed_by?: string; farmer_id?: string } | null;
  handovers: string[];
  completions: string[];
  can_accept?: boolean;
  my_farmer_id?: string;
}
export interface ExchangeMessage {
  id: string;
  sequence: number;
  text: string;
  farmer_id: string;
  sender_id?: string;
  display_name?: string;
  created_at: string;
  is_mine?: boolean;
}
export interface ExchangeEvent {
  id?: string;
  action?: string;
  event_type?: string;
  created_at: string;
  display_name?: string;
  details?: unknown;
  result?: {
    action_note?: string;
    proposal?: { terms: string };
    terms?: string;
  };
}
export async function exchangeRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await apiFetch(
    `${import.meta.env.VITE_API_URL || ""}/api/exchange${path}`,
    options,
  );
  const data = await response.json().catch(() => ({}));
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : `Could not complete this exchange (${response.status}).`,
    );
  return data;
}
export function exchangeWrite<T>(path: string, body: unknown, method = "POST") {
  return exchangeRequest<T>(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export type ExchangeAssistIntent =
  | "prepare_listing"
  | "compare_matches"
  | "draft_terms"
  | "review_exchange";
export interface ExchangeAssistDraft {
  kind: "listing" | "terms";
  fields?: Partial<
    Pick<
      ExchangeListing,
      | "title"
      | "category"
      | "kind"
      | "description"
      | "quantity"
      | "unit"
      | "state"
      | "district"
      | "exchange_for"
      | "available_on"
    >
  >;
  text?: string;
}
export interface ExchangeAssistResult {
  answer: string;
  draft?: ExchangeAssistDraft | null;
  saved: false;
  questions?: string[];
  requires_review?: boolean;
}
