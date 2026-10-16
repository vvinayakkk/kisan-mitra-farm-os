import { apiFetch } from "./apiClient";

const base = import.meta.env.VITE_API_URL || "";
export async function workspaceRequest<T>(
  path: string,
  method = "GET",
  body?: unknown,
  options: { signal?: AbortSignal; fresh?: boolean } = {},
): Promise<T> {
  const response = await apiFetch(`${base}${path}`, {
    method,
    signal: options.signal,
    cache: options.fresh ? "no-store" : undefined,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json().catch(() => ({}));
  const validationDetail = Array.isArray(data.detail)
    ? data.detail
        .map((item: { msg?: unknown }) =>
          typeof item.msg === "string" ? item.msg : "",
        )
        .filter(Boolean)
        .slice(0, 4)
        .join(" ")
    : "";
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : validationDetail ||
            `Could not ${method === "GET" ? "load" : "save"} this information (${response.status}).`,
    );
  return data;
}
