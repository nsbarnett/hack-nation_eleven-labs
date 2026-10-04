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
  let lastActivity = performance.now(), stopped = false, retry = 1000;
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
    socket.onopen = () => { retry = 1000; };
    socket.onmessage = (event) => {
      const value = JSON.parse(event.data);
      if (value.type !== "heartbeat") emit(value);
    };
    socket.onclose = () => {
      if (stopped) return;
      emit({ type: "backend-offline", message: "Connection interrupted. Capture has stopped; saved browser media is retained." });
      setTimeout(connect, retry);
      retry = Math.min(15000, retry * 2);
    };
  }
  async function reconcile() {
    if (!current?.guest || !current.session) return;
    for (const asset of await listAssets(current.guest, current.session.id)) {
      if (asset.name.endsWith(".webm") && asset.size && !current.session.recordings.includes(asset.name)) {
        await send("local-segment", { filename: asset.name });
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
      if (name === "delete-session" && !confirm("Delete this workflow, its hosted text, and media stored in this browser? This cannot be undone.")) return {};
      const result = await send(name, data);
      await load();
      if (before && current?.guest && ["forget", "delete-session"].includes(name)) {
        const retained = new Set(current.session?.evidence.map((e) => e.image) || []);
        const removed = new Set([...before.recordings, ...before.evidence.filter((e) => e.image && !retained.has(e.image)).map((e) => e.image)]);
        await removeAssets(current.guest, before.id, name === "delete-session" ? undefined : removed);
      }
      if (name === "open") { await reconcile(); await load(); }
      emit({ type: "state" });
      return result;
    },
    sources: async () => [],
    selectSource: async () => {},
    async beginSegment() {
      const owner = workflow(), filename = `${id()}.webm`;
      await beginAsset(owner.guest, owner.session, filename, "video/webm");
      segments.set(filename, owner);
      return filename;
    },
    async chunk(filename, bytes) {
      const owner = segments.get(filename);
      if (!owner) throw new Error("The recording segment is no longer open.");
      await appendAsset(owner.guest, owner.session, filename, bytes);
    },
    async endSegment(filename) {
      const owner = segments.get(filename);
      if (!owner) return;
      await finishAsset(owner.guest, owner.session, filename);
      const assets = await listAssets(owner.guest, owner.session);
      if (assets.find((a) => a.name === filename)?.size) await send("local-segment", { filename }, owner.session);
      segments.delete(filename);
    },
    async frame(bytes, duration) {
      const owner = workflow(), identifier = id(), filename = `${identifier}.jpg`;
      await beginAsset(owner.guest, owner.session, filename, "image/jpeg");
      await appendAsset(owner.guest, owner.session, filename, bytes);
      await finishAsset(owner.guest, owner.session, filename);
      if (current?.cloud) {
        const idle = media.voice === "listening" ? 0 : (performance.now() - lastActivity) / 1000;
        const query = new URLSearchParams({ sessionId: owner.session, id: identifier, duration: String(duration), idle: String(idle) });
        try { await api(`frame?${query}`, undefined, bytes); }
        catch (error) { await send("local-frame", { id: identifier, duration }, owner.session).catch(() => {}); throw error; }
      } else await send("local-frame", { id: identifier, duration }, owner.session);
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
      const owner = workflow(), blob = await readAsset(owner.guest, owner.session, name);
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
