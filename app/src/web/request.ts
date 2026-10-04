import { diagnostic } from "./diagnostics";

const actions: Record<string, string> = {
  state: "Refresh workspace", new: "Create workflow", open: "Open workflow", recover: "Reconnect workspace",
  note: "Save note or answer", "delete-session": "Delete workflow", "build-map": "Build Work Map",
  debrief: "Prepare question", "review-complete": "Prepare analysis question", "reviewer-tick": "Evaluate recording notes",
  reviewer: "Save reviewer preferences", recording: "Update recording state", "local-segment": "Save recording details",
  "reviewed-frame": "Analyze approved frame", speech: "Play reviewer voice", transcribe: "Transcribe voice answer",
  "privacy-reset": "Update privacy review", "privacy-approve": "Approve recording", practice: "Generate practice",
  tutor: "Evaluate practice answer", defer: "Save question for later", confirm: "Confirm Work Map",
  "edit-knowledge": "Save Work Map review", "review-gap": "Save expert clarification", forget: "Forget evidence",
};

export class HostedRequestError extends Error {
  constructor(message: string, readonly requestId: string, readonly category: string) { super(message); }
}

/** Read the entire response under the timeout so interrupted bodies are diagnosed too. */
export async function hostedRequest<T>(path: string, body?: unknown, raw?: Uint8Array, binary = false): Promise<T> {
  const endpoint = `/api/${path.split("?")[0]}`;
  const command = endpoint === "/api/command" && body && typeof body === "object" && "name" in body ? String(body.name) : path.split("?")[0];
  const operation = actions[command] || "Update workspace";
  const method = body !== undefined || raw ? "POST" : "GET";
  let requestId = crypto.randomUUID().replaceAll("-", "");
  const began = performance.now();
  let status: number | undefined;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 60_000);
  try {
    const response = await fetch(`/api/${path}`, {
      method, credentials: "same-origin", signal: controller.signal,
      headers: { "X-Apprentice-Client": "web", "X-Apprentice-Request-ID": requestId,
        ...(raw ? { "Content-Type": "application/octet-stream" } : body !== undefined ? { "Content-Type": "application/json" } : {}) },
      body: raw ? new Blob([new Uint8Array(raw)]) : body !== undefined ? JSON.stringify(body) : undefined,
    });
    status = response.status;
    const echoed = response.headers.get("X-Apprentice-Request-ID");
    if (echoed && /^[0-9a-f]{32}$/.test(echoed)) requestId = echoed;
    if (!response.ok) {
      const payload = await response.text();
      let detail = "";
      try { const error = JSON.parse(payload); if (typeof error.detail === "string") detail = error.detail; } catch { /* A proxy can return HTML. */ }
      const hint = status === 401 ? "Reload to reconnect your browser workspace." : status === 403 ? "Open the app from its own preview URL and retry." : status === 429 ? "Wait a moment before retrying." : status >= 500 ? "The server or its provider is unavailable. Check the server logs and retry." : "Review the action and retry.";
      throw new HostedRequestError(`${operation} failed (HTTP ${status}). ${detail || hint} Request ID: ${requestId}.`, requestId, "http");
    }
    const value = binary ? new Uint8Array(await response.arrayBuffer()) : await response.json();
    diagnostic({ event: "request_completed", operation, method, endpoint, requestId, status, elapsedMs: Math.round(performance.now() - began) });
    return value as T;
  } catch (error) {
    const category = error instanceof HostedRequestError ? error.category : controller.signal.aborted ? "timeout" : error instanceof SyntaxError ? "invalid_response" : navigator.onLine === false ? "offline" : "network";
    diagnostic({ event: "request_failed", operation, method, endpoint, requestId, status, category,
      online: navigator.onLine, elapsedMs: Math.round(performance.now() - began) });
    if (error instanceof HostedRequestError) throw error;
    const reason = category === "timeout" ? "The request timed out after 60 seconds." : category === "offline" ? "This browser is offline." : category === "invalid_response" ? "The server returned an unreadable response." : "The browser could not reach the app server or the connection was interrupted.";
    const recovery = method === "GET" ? "Reconnect or reload the preview." : "Reconnect and check the workflow before repeating the action; it may already have completed.";
    throw new HostedRequestError(`${operation} failed. ${reason} ${recovery} Request ID: ${requestId}.`, requestId, category);
  } finally { clearTimeout(timer); }
}
