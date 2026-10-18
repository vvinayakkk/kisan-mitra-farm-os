export const localPresentation = import.meta.env.VITE_LOCAL_PRESENTATION === "true" && import.meta.env.MODE !== "test";
// Include stored dated observations in every interface. Provenance stays visible.
export const reportedMarketsOnly = false;
