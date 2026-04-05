/**
 * Centralised env var access for all VITE_* variables.
 *
 * Reading from this module instead of `import.meta.env` directly gives:
 *  - a single place to see what env vars the frontend consumes
 *  - typed defaults (no scattered `?? '/api/v1'` in service files)
 *  - a startup warning when a production-required var is absent
 */

const _env = (import.meta as { env?: Record<string, string> }).env ?? {};

const get = (key: string, fallback = ""): string =>
  (_env[key] ?? fallback).replace(/\/$/, "");

// ---------------------------------------------------------------------------
// API / WebSocket base URLs
// ---------------------------------------------------------------------------

/** REST API base URL.  Defaults to the Vite dev-proxy path so requests
 *  stay same-origin and bypass CORS during local development. */
export const API_URL = get("VITE_API_URL", "/api/v1");

/** WebSocket base URL used for interview sessions.
 *  Falls back to VITE_FASTAPI_WS for backwards compat, then derives the
 *  origin from VITE_API_URL (http→ws / https→wss). */
export const WS_BASE_URL = (() => {
  const explicit =
    get("VITE_INTERVIEW_WS_URL") ||
    get("VITE_FASTAPI_WS") ||
    get("VITE_WS_URL");
  if (explicit) return explicit;

  const apiUrl = API_URL;
  if (/^https?:\/\//i.test(apiUrl)) {
    const origin = new URL(apiUrl).origin;
    return origin.replace(/^https?/, origin.startsWith("https") ? "wss" : "ws");
  }
  if (typeof window !== "undefined" && window.location?.origin) {
    const origin = window.location.origin;
    return origin.replace(/^https?/, origin.startsWith("https") ? "wss" : "ws");
  }
  return "ws://localhost:8000";
})();

// ---------------------------------------------------------------------------
// Billing / subscription
// ---------------------------------------------------------------------------

export const SUBSCRIPTION_MODE = get("VITE_SUBSCRIPTION_MODE", "hosted");
export const SUBSCRIPTION_SUCCESS_URL = get("VITE_SUBSCRIPTION_SUCCESS_URL");
export const SUBSCRIPTION_CANCEL_URL = get("VITE_SUBSCRIPTION_CANCEL_URL");
export const SUBSCRIPTION_API_FALLBACK = get("VITE_SUBSCRIPTION_API_FALLBACK");
export const HOSTED_CHECKOUT_PROVIDERS = get(
  "VITE_HOSTED_CHECKOUT_PROVIDERS",
  "stripe",
)
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);

// ---------------------------------------------------------------------------
// Startup validation — warns once in the browser console when vars that are
// required in production are missing.  Does not throw so it never breaks
// non-production builds.
// ---------------------------------------------------------------------------

const REQUIRED_IN_PRODUCTION: string[] = [
  "VITE_API_URL",
];

if (import.meta.env?.MODE === "production") {
  for (const key of REQUIRED_IN_PRODUCTION) {
    if (!_env[key]) {
      console.warn(
        `[env] Required environment variable "${key}" is not set. ` +
          "Falling back to a development default which may not work in production.",
      );
    }
  }
}
