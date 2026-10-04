/** Native bounds reserve animation space; React animates within those bounds. */
import { BrowserWindow, screen } from "electron";
export function overlayBounds(
  anchor: { x: number; y: number },
  expanded: boolean,
  question: boolean,
) {
  const display = screen.getDisplayNearestPoint(anchor).workArea;
  const width = expanded || question ? 420 : 104;
  const height = question ? 330 : 120;
  const x = Math.max(
    display.x,
    Math.min(anchor.x - width + 88, display.x + display.width - width),
  );
  const y = Math.max(
    display.y,
    Math.min(anchor.y - height + 88, display.y + display.height - height),
  );
  return { x: Math.round(x), y: Math.round(y), width, height };
}
export function createOverlay(preload: string) {
  const window = new BrowserWindow({
    width: 104,
    height: 120,
    show: false,
    frame: false,
    transparent: true,
    resizable: false,
    skipTaskbar: true,
    alwaysOnTop: true,
    focusable: false,
    hasShadow: false,
    webPreferences: {
      preload,
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
    },
  });
  window.setAlwaysOnTop(true, "floating");
  window.setContentProtection(true);
  return window;
}
