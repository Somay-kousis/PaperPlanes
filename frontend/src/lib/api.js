// ---------------------------------------------------------------------------
// PaperPlanes API client
//
// Thin fetch wrapper around the backend, mounted behind /api by both the Vite
// dev proxy (vite.config.js) and nginx in production (nginx.conf).
// ---------------------------------------------------------------------------

const BASE_URL = "/api";

class ApiError extends Error {
  constructor(message, { status, body } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

async function request(path, { method = "GET", body, headers, signal } = {}) {
  let response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers: {
        ...(body && !(body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
        Accept: "application/json",
        ...headers,
      },
      body: body
        ? body instanceof FormData
          ? body
          : JSON.stringify(body)
        : undefined,
      signal,
    });
  } catch (cause) {
    throw new ApiError("Could not reach the PaperPlanes backend. Is it running?", { cause });
  }

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json().catch(() => null)
    : await response.text().catch(() => null);

  if (!response.ok) {
    const message =
      (payload && typeof payload === "object" && (payload.detail || payload.message)) ||
      `Request failed with status ${response.status}`;
    throw new ApiError(message, { status: response.status, body: payload });
  }

  return payload;
}

// ---------------------------------------------------------------------------
// Sessions / chat
// ---------------------------------------------------------------------------

/**
 * GET /api/sessions returns `{items: [...]}`; normalize to a bare array so
 * callers don't need to know about the wrapper.
 */
export async function listSessions() {
  const data = await request("/sessions");
  return Array.isArray(data) ? data : (data?.items ?? []);
}

export function createSession(payload = {}) {
  return request("/sessions", { method: "POST", body: payload });
}

export function getSession(sessionId) {
  return request(`/sessions/${sessionId}`);
}

export function listMessages(sessionId) {
  return request(`/sessions/${sessionId}/messages`);
}

/**
 * Send a message and await the full JSON response:
 * `{session_id, reply: {role, content, created_at, citations}, meta: {degraded, used_model, rag}}`.
 */
export function sendMessage(sessionId, content) {
  return request(`/sessions/${sessionId}/messages`, {
    method: "POST",
    body: { content },
  });
}

/**
 * SSE-ready stub for streaming assistant replies.
 *
 * Once the backend exposes a streaming endpoint (e.g. text/event-stream at
 * `/sessions/{id}/messages/stream`), swap the implementation below for an
 * EventSource / fetch-stream reader. `onToken` is called with each partial
 * chunk, `onDone` with the final assembled message. Returns an unsubscribe
 * function so callers can cancel in-flight streams.
 */
export function streamMessage(sessionId, content, { onToken, onDone, onError } = {}) {
  let cancelled = false;

  sendMessage(sessionId, content)
    .then((response) => {
      if (cancelled) return;
      const reply = response?.reply ?? response;
      onToken?.(reply?.content ?? "");
      onDone?.(response);
    })
    .catch((error) => {
      if (!cancelled) onError?.(error);
    });

  return () => {
    cancelled = true;
  };
}

// ---------------------------------------------------------------------------
// Library / papers
// ---------------------------------------------------------------------------

/**
 * GET /api/papers returns `{items: [...]}`; normalize to a bare array.
 */
export async function listPapers() {
  const data = await request("/papers");
  return Array.isArray(data) ? data : (data?.items ?? []);
}

export function uploadPaper(file) {
  const form = new FormData();
  form.append("file", file);
  return request("/papers", { method: "POST", body: form });
}

/**
 * Add a paper from an arXiv ID or full arXiv URL — the backend accepts
 * either in the `arxiv_id` field.
 */
export function addArxivPaper(idOrUrl) {
  return request("/papers/arxiv", { method: "POST", body: { arxiv_id: idOrUrl } });
}

export function getPaperStatus(paperId) {
  return request(`/papers/${paperId}/status`);
}

export function deletePaper(paperId) {
  return request(`/papers/${paperId}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Memory inspector
// ---------------------------------------------------------------------------

/** Build a query string, skipping undefined/null/empty-string params. */
function buildQuery(params = {}) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, value);
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

/**
 * GET /api/memory/notes -> `{items: [...]}`; normalize to a bare array.
 * Supported params: status, as_of, q, limit.
 */
export async function getMemoryNotes(params = {}) {
  const data = await request(`/memory/notes${buildQuery(params)}`);
  return Array.isArray(data) ? data : (data?.items ?? []);
}

/** GET /api/memory/notes/{id} -> `{...note, links: [...], audit: [...]}`. */
export function getMemoryNote(id) {
  return request(`/memory/notes/${id}`);
}

/**
 * GET /api/memory/audit -> `{items: [...]}`; normalize to a bare array.
 * Supported params: target_id, action, since, limit.
 */
export async function getAudit(params = {}) {
  const data = await request(`/memory/audit${buildQuery(params)}`);
  return Array.isArray(data) ? data : (data?.items ?? []);
}

/** GET /api/memory/stats -> `{notes: {...}, audit_last_24h: {...}, links}`. */
export function getMemoryStats() {
  return request("/memory/stats");
}

// ---------------------------------------------------------------------------
// Contradictions
// ---------------------------------------------------------------------------

/**
 * GET /api/contradictions -> `{items: [...]}`; normalize to a bare array.
 * Supported params: resolved, limit.
 */
export async function getContradictions(params = {}) {
  const data = await request(`/contradictions${buildQuery(params)}`);
  return Array.isArray(data) ? data : (data?.items ?? []);
}

/**
 * POST /api/contradictions/{id}/resolve -> `{id, resolved:true, resolution_note}`.
 * `resolutionNote` is optional.
 */
export function resolveContradiction(id, resolutionNote) {
  return request(`/contradictions/${id}/resolve`, {
    method: "POST",
    body: resolutionNote ? { resolution_note: resolutionNote } : {},
  });
}

// ---------------------------------------------------------------------------
// Reflections
// ---------------------------------------------------------------------------

/** GET /api/reflections -> `{items: [...]}`; normalize to a bare array. */
export async function getReflections() {
  const data = await request("/reflections");
  return Array.isArray(data) ? data : (data?.items ?? []);
}

/** POST /api/reflections/run -> `{reflections_created, notes_archived, contradictions_found}`. */
export function runReflection() {
  return request("/reflections/run", { method: "POST" });
}

export { ApiError };
