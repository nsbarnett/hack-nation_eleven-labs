import {
  offline,
  validAction,
  validOrigin,
  validSnapshot,
  type Snapshot,
} from "./protocol";
let app: chrome.runtime.Port | undefined,
  snapshot: Snapshot = { ...offline },
  origin = "";
const surfaces = new Set<chrome.runtime.Port>(),
  seen = new Map<string, number>();
async function settings() {
  const value = (await chrome.storage.local.get("origin")).origin;
  origin = typeof value === "string" ? value : "";
}
void settings();
function broadcast(value: unknown) {
  for (const port of surfaces) {
    try {
      port.postMessage(value);
    } catch {
      surfaces.delete(port);
    }
  }
}
async function openApp() {
  await settings();
  if (!validOrigin(origin)) {
    await chrome.runtime.openOptionsPage();
    return;
  }
  const tabs = await chrome.tabs.query({ url: origin + "/*" });
  const existing = tabs.find((t) => t.id === app?.sender?.tab?.id) || tabs[0];
  if (existing?.id) {
    await chrome.tabs.update(existing.id, { active: true });
    if (existing.windowId)
      await chrome.windows.update(existing.windowId, { focused: true });
  } else await chrome.tabs.create({ url: origin });
}
chrome.runtime.onConnect.addListener((port) => {
  const frame = port.sender?.url || "";
  if (port.name === "app") {
    void settings().then(() => {
      if (
        !origin ||
        !frame.startsWith(origin + "/") ||
        port.sender?.frameId !== 0
      ) {
        port.disconnect();
        return;
      }
      // Exactly one workspace owner is accepted, matching the browser app lock.
      if (app && app.sender?.tab?.id !== port.sender?.tab?.id) {
        port.disconnect();
        return;
      }
      app = port;
      port.postMessage({ type: "snapshot-request" });
      port.onMessage.addListener((message) => {
        if (message.type === "snapshot" && validSnapshot(message.value)) {
          if (
            message.value.epoch === snapshot.epoch &&
            message.value.sequence < snapshot.sequence
          )
            return;
          snapshot = message.value;
          broadcast({ type: "snapshot", value: snapshot });
        } else if (message.type === "result" && typeof message.id === "string")
          broadcast({
            type: "result",
            id: message.id,
            error:
              typeof message.error === "string"
                ? message.error.slice(0, 500)
                : "",
          });
      });
      port.onDisconnect.addListener(() => {
        if (app === port) {
          app = undefined;
          snapshot = { ...offline };
          broadcast({ type: "snapshot", value: snapshot });
        }
      });
    });
  } else if (
    port.name === "surface" &&
    frame.startsWith(chrome.runtime.getURL(""))
  ) {
    surfaces.add(port);
    port.postMessage({ type: "snapshot", value: snapshot });
    port.onDisconnect.addListener(() => surfaces.delete(port));
    port.onMessage.addListener(async (message) => {
      if (!validAction(message) || seen.has(message.id)) return;
      seen.set(message.id, Date.now());
      for (const [id, at] of seen) if (Date.now() - at > 60000) seen.delete(id);
      if (message.action === "open") {
        await openApp();
        return;
      }
      if (!app || !snapshot.connected) {
        port.postMessage({
          type: "result",
          id: message.id,
          error: "Open Apprentice to reconnect.",
        });
        return;
      }
      if (
        message.epoch !== snapshot.epoch ||
        message.session !== snapshot.session ||
        message.question !== (snapshot.question?.id || null)
      ) {
        port.postMessage({
          type: "result",
          id: message.id,
          error:
            "The workflow or question changed. Try the current control again.",
        });
        return;
      }
      if (
        (message.action === "record" && snapshot.recording === "idle") ||
        message.action === "voice"
      )
        await openApp();
      app.postMessage(message);
    });
  }
});
async function register() {
  await chrome.scripting.unregisterContentScripts().catch(() => {});
  await settings();
  const permissions = await chrome.permissions.getAll();
  const matches = (permissions.origins || []).filter((x) =>
    x.startsWith("http"),
  );
  if (matches.length)
    await chrome.scripting.registerContentScripts([
      {
        id: "apprentice-orb",
        js: ["content.js"],
        matches,
        runAt: "document_idle",
        allFrames: false,
      },
    ]);
  // Existing tabs need immediate injection after explicit permission is granted.
  for (const tab of await chrome.tabs.query({}))
    if (tab.id && tab.url?.startsWith("http"))
      await chrome.scripting
        .executeScript({ target: { tabId: tab.id }, files: ["content.js"] })
        .catch(() => {});
}
chrome.permissions.onAdded.addListener(() => void register());
chrome.permissions.onRemoved.addListener(() => void register());
chrome.runtime.onInstalled.addListener(() => void register());
chrome.runtime.onStartup.addListener(() => void register());
chrome.storage.onChanged.addListener((changes) => {
  if (changes.origin) {
    app?.disconnect();
    app = undefined;
    snapshot = { ...offline };
    void register();
  }
});
chrome.action.onClicked.addListener(() => void openApp());
