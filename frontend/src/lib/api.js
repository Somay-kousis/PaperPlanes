// ---------------------------------------------------------------------------
// PaperPlanes API client for Swiss Brutalist workspace
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

// FastAPI's `detail` is a plain string for HTTPException but an array of
// {loc, msg, type} objects for 422 validation errors. Interpolating that
// straight into a banner renders "[object Object]", which tells the user
// nothing, so flatten the structured form into something readable.
function errorMessage(payload, status) {
  const fallback = `Request failed with status ${status}`;
  if (!payload || typeof payload !== "object") return fallback;

  const { detail } = payload;
  if (typeof detail === "string" && detail) return detail;

  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (!item || typeof item !== "object") return null;
        // Drop the leading "body"/"query" scope marker -- the field name is
        // the useful part.
        const field = Array.isArray(item.loc) ? item.loc.slice(1).join(".") : "";
        return field && item.msg ? `${field}: ${item.msg}` : (item.msg ?? null);
      })
      .filter(Boolean);
    if (parts.length) return parts.join("; ");
  }

  return payload.message || fallback;
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
    throw new ApiError(errorMessage(payload, response.status), {
      status: response.status,
      body: payload,
    });
  }

  return payload;
}

// ---------------------------------------------------------------------------
// Sessions / chat
// ---------------------------------------------------------------------------

export async function listSessions(options = {}) {
  const data = await request("/sessions", options);
  return Array.isArray(data) ? data : (data?.items ?? []);
}

export function createSession(payload = {}, options = {}) {
  return request("/sessions", { method: "POST", body: payload, ...options });
}

export function getSession(sessionId, options = {}) {
  return request(`/sessions/${sessionId}`, options);
}

export function listMessages(sessionId, options = {}) {
  return request(`/sessions/${sessionId}/messages`, options);
}

export function sendMessage(sessionId, content, options = {}) {
  return request(`/sessions/${sessionId}/messages`, {
    method: "POST",
    body: { content },
    ...options,
  });
}

// ---------------------------------------------------------------------------
// Library / papers
// ---------------------------------------------------------------------------

export async function listPapers(options = {}) {
  const data = await request("/papers", options);
  return Array.isArray(data) ? data : (data?.items ?? []);
}

export function uploadPaper(file, options = {}) {
  const form = new FormData();
  form.append("file", file);
  return request("/papers", { method: "POST", body: form, ...options });
}

export function addArxivPaper(idOrUrl, options = {}) {
  return request("/papers/arxiv", { method: "POST", body: { arxiv_id: idOrUrl }, ...options });
}

export function getPaperStatus(paperId, options = {}) {
  return request(`/papers/${paperId}/status`, options);
}

export function deletePaper(paperId, options = {}) {
  return request(`/papers/${paperId}`, { method: "DELETE", ...options });
}

// ---------------------------------------------------------------------------
// Memory inspector
// ---------------------------------------------------------------------------

function buildQuery(params = {}) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, value);
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export async function getMemoryNotes(params = {}, options = {}) {
  const data = await request(`/memory/notes${buildQuery(params)}`, options);
  return Array.isArray(data) ? data : (data?.items ?? []);
}

export function getMemoryNote(id, options = {}) {
  return request(`/memory/notes/${id}`, options);
}

export async function getAudit(params = {}, options = {}) {
  const data = await request(`/memory/audit${buildQuery(params)}`, options);
  return Array.isArray(data) ? data : (data?.items ?? []);
}

export function getMemoryStats(options = {}) {
  return request("/memory/stats", options);
}

// ---------------------------------------------------------------------------
// Contradictions
// ---------------------------------------------------------------------------

export async function getContradictions(params = {}, options = {}) {
  const data = await request(`/contradictions${buildQuery(params)}`, options);
  return Array.isArray(data) ? data : (data?.items ?? []);
}

export function resolveContradiction(id, resolutionNote, options = {}) {
  return request(`/contradictions/${id}/resolve`, {
    method: "POST",
    body: resolutionNote ? { resolution_note: resolutionNote } : {},
    ...options,
  });
}

// ---------------------------------------------------------------------------
// Reflections
// ---------------------------------------------------------------------------

export async function getReflections(options = {}) {
  const data = await request("/reflections", options);
  return Array.isArray(data) ? data : (data?.items ?? []);
}

export function runReflection(options = {}) {
  return request("/reflections/run", { method: "POST", ...options });
}

export { ApiError };
