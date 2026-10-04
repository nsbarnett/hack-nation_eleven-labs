/** Small explicit capabilities only. No generic IPC, paths, tokens, or Node APIs. */
import { contextBridge, ipcRenderer } from "electron";
const invoke = (channel: string, ...args: unknown[]) =>
  ipcRenderer.invoke(channel, ...args);
contextBridge.exposeInMainWorld("desktop", {
  platform: process.platform,
  quit: () => invoke("quit-ready"),
  state: () => invoke("state"),
  command: (name: string, data: unknown = {}) => invoke("command", name, data),
  sources: () => invoke("sources"),
  selectSource: (id: string) => invoke("select-source", id),
  beginSegment: () => invoke("begin-segment"),
  chunk: (id: string, bytes: Uint8Array) => invoke("chunk", id, bytes),
  endSegment: (id: string) => invoke("end-segment", id),
  frame: (bytes: Uint8Array, duration: number) =>
    invoke("frame", bytes, duration),
  speech: (text: string) => invoke("speech", text),
  transcribe: (bytes: Uint8Array) => invoke("transcribe", bytes),
  saveCredentials: (values: Record<string, string>) =>
    invoke("credentials", values),
  checkCredentials: (provider: string) => invoke("check-credentials", provider),
  importLegacy: () => invoke("import"),
  exportMap: () => invoke("export"),
  media: (relative: string) => invoke("media", relative),
  window: (action: string) => invoke("window", action),
  overlay: (expanded: boolean, question: boolean) =>
    invoke("overlay", expanded, question),
  drag: (dx: number, dy: number) => invoke("drag", dx, dy),
  passthrough: (enabled: boolean) => invoke("passthrough", enabled),
  relay: (action: string) => invoke("relay", action),
  status: (status: unknown) => invoke("status", status),
  onEvent: (callback: (event: any) => void) => {
    const listener = (_event: unknown, data: unknown) => callback(data);
    ipcRenderer.on("event", listener);
    return () => ipcRenderer.removeListener("event", listener);
  },
});
