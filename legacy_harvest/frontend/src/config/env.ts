const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();

/** Empty in same-origin deployments; configurable for a separately hosted API. */
export const apiBaseUrl = configuredBaseUrl ? configuredBaseUrl.replace(/\/$/, "") : "";
