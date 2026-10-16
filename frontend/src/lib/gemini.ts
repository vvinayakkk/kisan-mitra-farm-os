import { apiFetch } from "@/lib/apiClient";
export async function getGeminiResponse(prompt: string, contextData?: unknown): Promise<string> {
  const backendUrl = import.meta.env.VITE_API_URL || "";
  const response = await apiFetch(`${backendUrl}/api/chat`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: prompt, context: contextData }) });
  if (!response.ok) throw new Error("The farm assistant could not respond. Please retry.");
  const data = await response.json();
  if (typeof data.response !== "string" || !data.response.trim()) throw new Error("No answer was returned. Please retry.");
  return data.response;
}
