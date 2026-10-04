/** Desktop authority: validates IPC, owns OS resources, proxies the local service. */
import {
  app,
  BrowserWindow,
  desktopCapturer,
  dialog,
  ipcMain,
  session,
  screen,
  powerMonitor,
  nativeTheme,
  shell,
  Menu,
  powerSaveBlocker,
  globalShortcut,
} from "electron";
import { promises as fs } from "node:fs";
import { randomUUID } from "node:crypto";
import path from "node:path";
import { Backend } from "./backend";
import { Credentials } from "./credentials";
import { createOverlay, overlayBounds } from "./overlayWindow";

let main: BrowserWindow;
let overlay: BrowserWindow;
let backend: Backend;
let closing = false;
let selected = "";
let anchor = { x: 0, y: 0 };
let expanded = false;
let questionVisible = false;
let blocker: number | undefined;
let root = "";
let mediaStatus: any = {
  state: "idle",
  muted: true,
  voice: "idle",
  duration: 0,
};
const segments = new Map<
  string,
  { file: fs.FileHandle; filename: string; sessionId: string }
>();
const commands = new Set([
  "new",
  "open",
  "cloud",
  "recording",
  "note",
  "defer",
  "build-map",
  "debrief",
  "edit-knowledge",
  "confirm",
  "forget",
  "practice",
  "tutor",
  "coaching",
]);
function send(event: unknown) {
  for (const window of [main, overlay])
    if (window && !window.isDestroyed())
      window.webContents.send("event", event);
}
function clampOverlay() {
  overlay.setBounds(overlayBounds(anchor, expanded, questionVisible));
  const b = overlay.getBounds();
  anchor = { x: b.x + b.width - 88, y: b.y + b.height - 88 };
}
function safeMedia(sessionId: string, relative: string) {
  if (!/^[a-f0-9]{32}$/.test(sessionId)) throw new Error("Invalid session.");
  const base = path.join(root, "sessions", sessionId),
    target = path.resolve(base, relative);
  if (!target.startsWith(base + path.sep))
    throw new Error("Invalid media path.");
  return target;
}
function handler(
  name: string,
  action: (...args: any[]) => any,
  mainOnly = false,
) {
  ipcMain.handle(name, async (event, ...args) => {
    const owner = BrowserWindow.fromWebContents(event.sender);
    if (
      !owner ||
      (owner !== main && owner !== overlay) ||
      event.senderFrame !== event.sender.mainFrame ||
      (mainOnly && owner !== main)
    )
      throw new Error("Unauthorized window.");
    return action(...args);
  });
}
if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on("second-instance", () => {
    main?.show();
    main?.focus();
  });
  app
    .whenReady()
    .then(async () => {
      nativeTheme.themeSource = "light";
      Menu.setApplicationMenu(
        process.platform === "darwin"
          ? Menu.buildFromTemplate([
              { role: "appMenu" },
              { role: "editMenu" },
              { role: "windowMenu" },
            ])
          : null,
      );
      root =
        process.env.APPRENTICE_DATA_DIR ||
        path.join(app.getPath("userData"), "data");
      await fs.mkdir(root, { recursive: true });
      backend = new Backend(root);
      const preload = path.join(__dirname, "preload.js");
      main = new BrowserWindow({
        width: 1320,
        height: 880,
        minWidth: 1000,
        minHeight: 700,
        show: false,
        title: "AI Apprentice",
        icon: path.join(__dirname, "../assets/icon.png"),
        backgroundColor: "#ffffff",
        titleBarStyle: "hidden",
        titleBarOverlay:
          process.platform === "win32"
            ? { color: "#ffffff", symbolColor: "#111111", height: 38 }
            : undefined,
        webPreferences: {
          preload,
          nodeIntegration: false,
          contextIsolation: true,
          sandbox: true,
          backgroundThrottling: false,
        },
      });
      overlay = createOverlay(preload);
      for (const window of [main, overlay]) {
        window.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
        window.webContents.on("will-navigate", (event) =>
          event.preventDefault(),
        );
      }
      main.setContentProtection(true);
      const work = screen.getPrimaryDisplay().workArea;
      anchor = { x: work.x + work.width - 130, y: work.y + work.height - 140 };
      try {
        anchor = JSON.parse(
          await fs.readFile(path.join(root, "overlay-position.json"), "utf8"),
        );
      } catch {
        /* First launch. */
      }
      clampOverlay();
      screen.on("display-metrics-changed", clampOverlay);
      screen.on("display-removed", clampOverlay);
      backend.onEvent = send;
      await backend.start();
      const credentials = new Credentials(path.join(root, "credentials.enc"));
      try {
        await backend.request("/command", {
          name: "credentials",
          data: await credentials.read(),
        });
      } catch {
        dialog.showErrorBox(
          "Credential storage",
          "Saved credentials could not be unlocked. You can replace them in Settings.",
        );
      }

      handler("state", async () => ({
        ...(await backend.request("/state")),
        media: mediaStatus,
        version: app.getVersion(),
      }));
      handler("command", async (name, data) => {
        if (!commands.has(name)) throw new Error("Unknown command.");
        if (name === "forget") {
          const answer = await dialog.showMessageBox(main, {
            type: "warning",
            buttons: ["Cancel", "Forget evidence"],
            defaultId: 0,
            cancelId: 0,
            message: "Forget this evidence?",
            detail:
              "This removes its dependent answers, the derived Work Map, and all raw videos in this session. Exported copies are not removed.",
          });
          if (answer.response !== 1) return { cancelled: true };
        }
        return backend.request("/command", { name, data });
      });
      handler(
        "sources",
        async () => {
          const sources = await desktopCapturer.getSources({
            types: ["screen", "window"],
            thumbnailSize: { width: 320, height: 180 },
          });
          return sources
            .filter((s) => !s.name.startsWith("AI Apprentice"))
            .map((s) => ({
              id: s.id,
              name: s.name,
              thumbnail: s.thumbnail.toDataURL(),
              displayId: s.display_id,
            }));
        },
        true,
      );
      handler(
        "select-source",
        (id: string) => {
          selected = id;
        },
        true,
      );
      session.defaultSession.setPermissionRequestHandler(
        (contents, permission, callback, details) => {
          const mediaTypes =
            ("mediaTypes" in details ? details.mediaTypes : []) || [];
          callback(
            contents === main.webContents &&
              (permission === "display-capture" ||
                (permission === "media" && !mediaTypes.includes("video"))),
          );
        },
      );
      session.defaultSession.setPermissionCheckHandler(
        (contents, permission) =>
          contents === main.webContents &&
          ["media", "display-capture"].includes(permission),
      );
      session.defaultSession.setDisplayMediaRequestHandler(
        async (request, callback) => {
          if (request.frame !== main.webContents.mainFrame || !selected)
            return callback({});
          try {
            const sources = await desktopCapturer.getSources({
              types: ["screen", "window"],
            });
            const source = sources.find((s) => s.id === selected);
            callback(source ? { video: source } : {});
          } catch {
            callback({});
          }
        },
      );
      handler(
        "begin-segment",
        async () => {
          if (segments.size)
            throw new Error("A recording segment is already open.");
          const state = await backend.request("/state");
          if (!state.session) throw new Error("Create a workflow first.");
          const id = randomUUID(),
            filename = `recording-${id}.webm`;
          const dest = safeMedia(state.session.id, filename);
          await fs.mkdir(path.dirname(dest), { recursive: true });
          const file = await fs.open(dest, "wx");
          segments.set(id, { file, filename, sessionId: state.session.id });
          return id;
        },
        true,
      );
      handler(
        "chunk",
        async (id: string, bytes: Uint8Array) => {
          const segment = segments.get(id);
          if (
            !segment ||
            !(bytes instanceof Uint8Array) ||
            bytes.byteLength > 16 * 1024 * 1024
          )
            throw new Error("Invalid recording chunk.");
          const buffer = Buffer.from(bytes);
          let offset = 0;
          while (offset < buffer.length) {
            const result = await segment.file.write(
              buffer,
              offset,
              buffer.length - offset,
            );
            if (!result.bytesWritten)
              throw new Error("Recording disk write failed.");
            offset += result.bytesWritten;
          }
        },
        true,
      );
      handler(
        "end-segment",
        async (id: string) => {
          const segment = segments.get(id);
          if (!segment) return;
          segments.delete(id);
          await segment.file.close();
          const state = await backend.request("/state");
          if (state.session?.id !== segment.sessionId)
            throw new Error("Session changed while recording.");
          await backend.request("/command", {
            name: "segment",
            data: { filename: segment.filename },
          });
        },
        true,
      );
      handler(
        "frame",
        (bytes: Uint8Array, duration: number) =>
          backend.request(
            `/frame?duration=${Math.max(0, duration)}&idle=${mediaStatus.voice === "idle" ? powerMonitor.getSystemIdleTime() : 0}`,
            undefined,
            bytes,
          ),
        true,
      );
      handler(
        "speech",
        (text: string) => backend.request("/speech", { text }),
        true,
      );
      handler(
        "transcribe",
        (bytes: Uint8Array) => backend.request("/transcribe", undefined, bytes),
        true,
      );
      handler(
        "credentials",
        async (values: Record<string, string>) => {
          if (
            !Object.keys(values).every((k) =>
              ["openai_key", "eleven_key", "voice_id", "model"].includes(k),
            ) ||
            !Object.values(values).every(
              (v) => typeof v === "string" && v.length <= 1000,
            )
          )
            throw new Error("Invalid settings.");
          const saved = await credentials.save(values);
          await backend.request("/command", {
            name: "credentials",
            data: saved,
          });
        },
        true,
      );
      handler(
        "check-credentials",
        (provider: string) => {
          if (!["openai", "elevenlabs"].includes(provider))
            throw new Error("Unknown provider.");
          return backend.request("/check-credentials", { provider });
        },
        true,
      );
      handler(
        "import",
        async () => {
          const result = await dialog.showOpenDialog(main, {
            title: "Select legacy AI Apprentice data folder",
            properties: ["openDirectory"],
          });
          return result.canceled
            ? { count: 0 }
            : backend.request("/import", { path: result.filePaths[0] });
        },
        true,
      );
      handler(
        "export",
        async () => {
          const result = await dialog.showOpenDialog(main, {
            title: "Choose export destination",
            properties: ["openDirectory", "createDirectory"],
          });
          if (result.canceled) return {};
          const exported = await backend.request("/export", {
            path: result.filePaths[0],
          });
          await shell.openPath(exported.path);
          return exported;
        },
        true,
      );
      handler(
        "media",
        async (relative: string) => {
          const state = await backend.request("/state");
          if (!state.session) throw new Error("No session.");
          const allowed = [
            ...state.session.recordings,
            ...state.session.evidence.map((e: any) => e.image),
          ];
          if (!allowed.includes(relative))
            throw new Error("Media is not part of this session.");
          const file = safeMedia(state.session.id, relative);
          if (!/\.(jpg|jpeg|png|webm|mp4)$/i.test(relative))
            throw new Error("Unsupported media type.");
          if (relative.endsWith(".jpg"))
            return (
              "data:image/jpeg;base64," +
              (await fs.readFile(file)).toString("base64")
            );
          await shell.openPath(file);
          return null;
        },
        true,
      );
      handler("window", (action: string) => {
        if (action === "open") {
          main.show();
          main.focus();
        }
        if (action === "minimize") main.minimize();
        if (action === "close") main.close();
      });
      handler("overlay", (open: boolean, question: boolean) => {
        expanded = !!open;
        questionVisible = !!question;
        clampOverlay();
      });
      handler("drag", (dx: number, dy: number) => {
        if (!Number.isFinite(dx) || !Number.isFinite(dy)) return;
        anchor.x += Math.max(-100, Math.min(100, dx));
        anchor.y += Math.max(-100, Math.min(100, dy));
        clampOverlay();
        void fs
          .writeFile(
            path.join(root, "overlay-position.json"),
            JSON.stringify(anchor),
          )
          .catch(() => {});
      });
      handler("passthrough", (enabled: boolean) =>
        overlay.setIgnoreMouseEvents(!!enabled, { forward: true }),
      );
      handler("relay", (action: string) => {
        if (!["record", "context", "voice", "mute", "open"].includes(action))
          return;
        if (["context", "open"].includes(action)) {
          main.show();
          main.focus();
        }
        main.webContents.send("event", { type: "action", action });
      });
      handler(
        "status",
        (status: any) => {
          mediaStatus = {
            state: status.state,
            muted: !!status.muted,
            voice: status.voice,
            duration: Number(status.duration) || 0,
          };
          if (mediaStatus.state === "recording" && blocker === undefined)
            blocker = powerSaveBlocker.start("prevent-app-suspension");
          if (mediaStatus.state !== "recording" && blocker !== undefined) {
            powerSaveBlocker.stop(blocker);
            blocker = undefined;
          }
          send({ type: "media", media: mediaStatus });
        },
        true,
      );
      main.on("minimize", () => overlay.showInactive());
      main.on("close", (event) => {
        if (!closing) {
          event.preventDefault();
          main.webContents.send("event", { type: "closing" });
        }
      });
      main.webContents.on("render-process-gone", () => {
        void backend.request("/command", {
          name: "recording",
          data: { state: "idle" },
        });
      });
      handler(
        "quit-ready",
        () => {
          closing = true;
          app.quit();
        },
        true,
      );
      await main.loadFile(path.join(__dirname, "../dist/index.html"));
      await overlay.loadFile(path.join(__dirname, "../dist/index.html"), {
        hash: "overlay",
      });
      main.show();
      overlay.showInactive();
      globalShortcut.register("CommandOrControl+Shift+Space", () => {
        overlay.setFocusable(true);
        overlay.show();
        overlay.focus();
      });
      overlay.on("blur", () => overlay.setFocusable(false));
      app.on("activate", () => {
        main.show();
        main.focus();
      });
    })
    .catch((error) => {
      dialog.showErrorBox(
        "AI Apprentice could not start",
        String(error.message),
      );
      closing = true;
      app.quit();
    });
}
app.on("before-quit", (event) => {
  if (!closing && main && !main.isDestroyed()) {
    event.preventDefault();
    main.webContents.send("event", { type: "closing" });
    return;
  }
  closing = true;
  globalShortcut.unregisterAll();
  backend?.stop();
  for (const segment of segments.values()) void segment.file.close();
});
app.on("window-all-closed", () => app.quit());
