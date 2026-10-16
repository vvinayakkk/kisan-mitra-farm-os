/** Personal local-workspace presentation; source metadata remains in API records. */
export const localPresentation = import.meta.env.VITE_LOCAL_PRESENTATION === "true" && import.meta.env.MODE !== "test";
export const reportedMarketsOnly = !localPresentation;
