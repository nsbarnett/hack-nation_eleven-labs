/** Browser implementation of the existing narrow renderer bridge.
 * Capture bytes stay in IndexedDB. Only opted-in frames and explicit voice
 * answers cross the same-origin API; credentials never enter this module.
 */
import type { Desktop, State, MediaStatus } from "../types";
import { appendAsset, beginAsset, finishAsset, listAssets, readAsset, removeAssets } from "./localMedia";
const id = () => crypto.randomUUID().replaceAll("-", "");
const emptyMedia: MediaStatus = { state: "idle", muted: true, voice: "idle", duration: 0 };

export function createWebBridge(): Desktop {
  let current: State | null = null, media = { ...emptyMedia }, initialized = false;
  let initialization: Promise<void> | undefined, socket: WebSocket | undefined;
  let ownsTab = false, fetchSerial = 0, appliedSerial = 0;
  let lastActivity = performance.now(), stopped = false, retry = 1000, interrupted = false;
  const callbacks = new Set<(event: any) => void>();
  const segments = new Map<string, { guest: string; session: string }>();
  const urls = new Set<string>();
  const emit = (event: any) => callbacks.forEach((callback) => callback(event));
  for (const event of ["pointerdown", "keydown", "pointermove"]) {
    window.addEventListener(event, () => { lastActivity = performance.now(); }, { passive: true });
  }
  async function api(path: string, body?: unknown, raw?: Uint8Array): Promise<Response> {
    const response = await fetch(`/api/${path}`, {
      method: body !== undefined || raw ? "POST" : "GET",
      credentials: "same-origin",
      signal: AbortSignal.timeout(60_000),
      headers: { "X-Apprentice-Client": "web", ...(raw ? { "Content-Type": "application/octet-stream" } : body !== undefined ? { "Content-Type": "application/json" } : {}) },
      body: raw ? new Blob([new Uint8Array(raw)]) : body !== undefined ? JSON.stringify(body) : undefined,
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(typeof error.detail === "string" ? error.detail : `The hosted request failed (${response.status}). Try again.`);
    }
    return response;
  }
  async function load() {
    const serial = ++fetchSerial;
    const result: State = await (await api("state")).json();
    if (serial >= appliedSerial) { current = { ...result, media }; appliedSerial = serial; }
    return current!;
  }
  async function send(name: string, data: unknown = {}, sessionId = current?.session?.id) {
    return (await api("command", { name, data, sessionId })).json();
  }
  function connect() {
    if (stopped) return;
    socket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/events`);
    socket.onopen = () => {
      retry = 1000;
      if (interrupted) {
        interrupted = false;
        // Track shutdown happens immediately on disconnect. The final HTTP
        // command may have failed, so reset the server's capture state too.
        void send("recover").then(reconcile).then(load).then(() => emit({ type: "resync" }))
          .catch((error) => emit({ type: "error", message: String(error) }));
      }
    };
    socket.onmessage = (event) => {
      const value = JSON.parse(event.data);
      if (value.type !== "heartbeat") emit(value);
    };
    socket.onclose = () => {
      if (stopped) return;
      interrupted = true;
      emit({ type: "backend-offline", message: "Connection interrupted. Capture has stopped; saved browser media is retained." });
      setTimeout(connect, retry);
      retry = Math.min(15000, retry * 2);
    };
  }
  async function reconcile() {
    if (!current?.guest || !current.session) return;
    for (const asset of await listAssets(current.guest, current.session.id)) {
      if (asset.purpose !== "redacted" && asset.name.endsWith(".webm") && asset.size && !current.session.recordings.includes(asset.name)) {
        await send("local-segment", { filename: asset.name, ...(asset.duration !== undefined ? { start: asset.start || 0, duration: asset.duration } : {}) });
      }
    }
  }
  async function initialize() {
    if (initialized) return;
    return (initialization ??= (async () => {
      if (!window.isSecureContext || !navigator.locks) throw new Error("Open this app over HTTPS in Chrome or Edge.");
      if (!ownsTab) await new Promise<void>((resolve, reject) => {
        void navigator.locks.request("apprentice-web-workspace", { ifAvailable: true }, async (lock) => {
          if (!lock) { reject(new Error("Apprentice is already open in another tab. Use that tab or close it and reload here.")); return; }
          ownsTab = true; resolve();
          await new Promise<void>(() => {}); // Browser releases this lock on tab close.
        }).catch(reject);
      });
      await load();
      await send("recover");
      if (current?.guest) {
        const prefix = `apprentice-delete:${current.guest}:`;
        const pending = Object.keys(localStorage).filter((key) => key.startsWith(prefix));
        for (const key of pending) {
          const target = key.slice(prefix.length);
          if (!/^[0-9a-f]{32}$/.test(target)) continue;
          if (current.sessions.some((s) => s.id === target)) await send("delete-session", { id: target, confirmed: true });
          await removeAssets(current.guest, target);
          localStorage.removeItem(key);
        }
        if (pending.length) await load();
      }
      await reconcile();
      initialized = true;
      connect();
    })().catch((error) => { initialization = undefined; throw error; }));
  }
  function workflow() {
    if (!current?.session || !current.guest) throw new Error("Create or open a workflow first.");
    return { session: current.session.id, guest: current.guest };
  }
  window.addEventListener("beforeunload", (event) => {
    if (media.state !== "idle") { event.preventDefault(); event.returnValue = ""; }
  });
  window.addEventListener("pagehide", () => { stopped = true; socket?.close(); urls.forEach((url) => URL.revokeObjectURL(url)); });
  return {
    platform: "web",
    async state() { await initialize(); return load(); },
    async command(name, data: any = {}) {
      await initialize();
      const before = current?.session;
      if (name === "forget" && !confirm("Forget this evidence? Derived knowledge and this workflow's recordings will be removed. This cannot be undone.")) return {};
      if (name === "delete-session") {
        if (data.confirmed !== true || !current?.guest || !/^[0-9a-f]{32}$/.test(data.id)) throw new Error("Confirm the selected workflow's deletion.");
        const guest = current.guest, target = data.id;
        const key = `apprentice-delete:${guest}:${target}`;
        if (!localStorage.getItem(key) && !current.sessions.some((s) => s.id === target)) throw new Error("This workflow is no longer available.");
        const privacy = await import("../privacy/service");
        await privacy.prepareWorkflowDeletion(guest, target);
        try {
          localStorage.setItem(key, "pending");
          if (current.sessions.some((s) => s.id === target)) {
            try { await send(name, data); }
            catch (error) {
              await load();
              if (current!.sessions.some((s) => s.id === target)) {
                localStorage.removeItem(key);
                throw error;
              }
            }
          }
          await removeAssets(guest, target);
          localStorage.removeItem(key);
          await load(); emit({ type: "state" });
          return {};
        } finally { privacy.finishWorkflowDeletion(target); }
      }
      const result = await send(name, data);
      await load();
      if (before && current?.guest && name === "forget") {
        const retained = new Set(current.session?.evidence.map((e) => e.image) || []);
        await removeAssets(current.guest, before.id);
      }
      if (name === "open") { await reconcile(); await load(); }
      emit({ type: "state" });
      return result;
    },
    sources: async () => [],
    selectSource: async () => {},
    async beginSegment(metadata) {
      const { usePrivacyJobs } = await import('../privacy/service');
      if (usePrivacyJobs.getState().label) throw new Error('Finish or cancel privacy processing before starting another recording.');
      const owner = workflow(), filename = `${id()}.webm`;
      await beginAsset(owner.guest, owner.session, filename, "video/webm", { purpose: "source", ...metadata });
      segments.set(filename, owner);
      return filename;
    },
    async chunk(filename, bytes) {
      const owner = segments.get(filename);
      if (!owner) throw new Error("The recording segment is no longer open.");
      await appendAsset(owner.guest, owner.session, filename, bytes);
    },
    async endSegment(filename, duration, partial = false) {
      const owner = segments.get(filename);
      if (!owner) return;
      await finishAsset(owner.guest, owner.session, filename, { duration, partial });
      const assets = await listAssets(owner.guest, owner.session);
      const asset = assets.find(a => a.name === filename);
      if (asset?.size) await send("local-segment", { filename, ...(duration !== undefined ? { start: asset.start || 0, duration } : {}) }, owner.session);
      segments.delete(filename);
    },
    async frame(bytes, duration) {
      const owner = workflow(), filename = `${id()}.jpg`;
      const activeSegment = [...segments.keys()].at(-1);
      if (!activeSegment) return;
      const assets = await listAssets(owner.guest, owner.session);
      const start = assets.find(a => a.name === activeSegment)?.start || 0;
      // Raw bytes and OCR results stay in IndexedDB/local workers, including
      // when cloud analysis is enabled. No server frame request occurs here.
      await beginAsset(owner.guest, owner.session, filename, "image/jpeg", { purpose: "source", timestamp: duration });
      await appendAsset(owner.guest, owner.session, filename, bytes);
      await finishAsset(owner.guest, owner.session, filename);
      const { detectLive } = await import('../privacy/service');
      void detectLive(owner.guest, owner.session, activeSegment, Math.max(0, duration - start), new Blob([new Uint8Array(bytes)], { type: 'image/jpeg' }));
    },
    async reviewedFrame(bytes, duration, identifier, sessionId, revision) {
      const query = new URLSearchParams({ sessionId, id: identifier, duration: String(duration), revision: String(revision) });
      await api(`reviewed-frame?${query}`, undefined, bytes);
    },
    async speech(text) { const response = await api("speech", { text, sessionId: workflow().session }); return new Uint8Array(await response.arrayBuffer()); },
    async transcribe(bytes) { return (await api(`transcribe?sessionId=${workflow().session}`, undefined, bytes)).json(); },
    saveCredentials: async () => { throw new Error("Hosted connections are managed by the app owner."); },
    checkCredentials: async () => { throw new Error("Hosted connections are managed by the app owner."); },
    importLegacy: async () => { throw new Error("Legacy import is available in the desktop edition."); },
    async exportMap() {
      if (!current?.session) throw new Error("Open a workflow first.");
      const blob = new Blob([JSON.stringify(current.session, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob), anchor = document.createElement("a");
      anchor.href = url; anchor.download = `${current.session.title.replace(/[^a-z0-9_-]/gi, "-")}-work-map.json`;
      anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
      return {};
    },
    async media(name) {
      const owner = workflow();
      const { readReview } = await import('./localMedia');
      const review = await readReview(owner.guest, owner.session);
      if (review?.status !== 'approved' || review.revision !== current?.session?.privacy.revision || current.session.privacy.status !== 'approved') throw new Error('Review and approve privacy edits before playback or download. Originals are available only in Privacy Review.');
      const filename = review.derivatives[name] || name;
      const asset = (await listAssets(owner.guest, owner.session)).find(a => a.name === filename);
      if (asset?.purpose !== 'redacted' || asset.partial || asset.revision !== review.revision) throw new Error('No approved redacted copy is available. Open Privacy Review to render it.');
      const blob = await readAsset(owner.guest, owner.session, filename);
      const url = URL.createObjectURL(blob); urls.add(url); return url;
    },
    window: async () => { window.focus(); },
    overlay: async () => {}, drag: async () => {}, passthrough: async () => {},
    relay: async (action) => { emit({ type: "action", action }); },
    status: async (value) => { media = value; },
    onEvent(callback) { callbacks.add(callback); return () => { callbacks.delete(callback); }; },
    quit: async () => {},
  };
}
