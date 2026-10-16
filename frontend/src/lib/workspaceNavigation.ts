/** Explicit classic routes keep entry and return navigation local and predictable. */
export const classicWorkspaceViews: Record<string, string> = {
  dashboard: "chat", "crop-doctor": "crops", trends: "markets",
  reports: "records", advisor: "chat", overview: "station",
  accelerator: "station", mandi: "markets", db: "records",
  marketplace: "exchange", map: "exchange", profile: "profile",
  "hardware-setup": "station", "buy-hardware": "station",
};
export function workspaceDestination(pathname: string) {
  const origin = pathname.replace(/^\//, "");
  if (!Object.prototype.hasOwnProperty.call(classicWorkspaceViews, origin)) return null;
  return `/workspace?view=${classicWorkspaceViews[origin]}&from=${origin}`;
}
export function classicDestination(origin: string | null) {
  return origin && Object.prototype.hasOwnProperty.call(classicWorkspaceViews, origin) ? `/${origin}` : "/advisor";
}
