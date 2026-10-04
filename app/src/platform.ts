/** Install the browser capability adapter only when Electron has no preload. */
import { createWebBridge } from "./web/bridge";
if (!window.desktop) window.desktop = createWebBridge();
export const hosted = window.desktop.platform === "web";
