/** Isolated world. Host pages receive geometry messages only, never note text. */
import { validAction, validSnapshot } from "./protocol";
declare global {
  interface Window {
    __apprenticeOrb?: boolean;
  }
}
if (!window.__apprenticeOrb) {
  window.__apprenticeOrb = true;
  void chrome.storage.local.get(["origin", "position"]).then((config) => {
    if (location.origin === config.origin) {
      let port: chrome.runtime.Port | undefined;
      const connect = () => {
        try {
          port = chrome.runtime.connect({ name: "app" });
          port.onMessage.addListener((message) => {
            if (message.type === "snapshot-request" || validAction(message))
              window.postMessage(
                { source: "apprentice-extension", value: message },
                location.origin,
              );
          });
          port.onDisconnect.addListener(() => {
            port = undefined;
            setTimeout(connect, 2000);
          });
          window.postMessage(
            {
              source: "apprentice-extension",
              value: { type: "snapshot-request" },
            },
            location.origin,
          );
        } catch {
          /* Extension was reloaded; reload this tab. */
        }
      };
      window.addEventListener("message", (event) => {
        if (
          event.source !== window ||
          event.origin !== location.origin ||
          event.data?.source !== "apprentice-app"
        )
          return;
        const message = event.data.value;
        if (
          (message?.type === "snapshot" && validSnapshot(message.value)) ||
          (message?.type === "result" && typeof message.id === "string")
        )
          port?.postMessage(message);
      });
      connect();
      return;
    }
    const root = document.createElement("div");
    const shadow = root.attachShadow({ mode: "closed" });
    // Independent iframes occupy only their visible rectangles. No full-page
    // transparent iframe intercepts clicks. The orb is never removed/resized.
    root.style.cssText =
      "position:fixed!important;inset:0!important;pointer-events:none!important;z-index:2147483647!important;";
    const frames = ["orb", "bar", "card"].map((surface) => {
      const iframe = document.createElement("iframe");
      iframe.src = chrome.runtime.getURL(`surface.html#${surface}`);
      iframe.title = `Apprentice ${surface}`;
      iframe.style.cssText =
        "position:absolute;border:0;background:transparent;color-scheme:light;pointer-events:auto;";
      shadow.append(iframe);
      return iframe;
    });
    document.documentElement.append(root);
    const position = config.position as { x?: number; y?: number } | undefined;
    let x =
        typeof position?.x === "number" && Number.isFinite(position.x)
          ? position.x
          : innerWidth - 88,
      y =
        typeof position?.y === "number" && Number.isFinite(position.y)
          ? position.y
          : innerHeight - 120,
      expanded = false,
      card = false;
    let hideTimer: ReturnType<typeof setTimeout> | undefined;
    function layout() {
      x = Math.max(8, Math.min(innerWidth - 80, x));
      y = Math.max(8, Math.min(innerHeight - 80, y));
      Object.assign(frames[0].style, {
        left: `${x}px`,
        top: `${y}px`,
        width: "72px",
        height: "72px",
        clipPath: "circle(33px at 36px 36px)",
      });
      const left = x >= 320 ? x - 314 : Math.min(innerWidth - 308, x + 76);
      clearTimeout(hideTimer);
      Object.assign(frames[1].style, {
        left: `${Math.max(0, left)}px`,
        top: `${y}px`,
        width: "308px",
        height: "88px",
        pointerEvents: expanded ? "auto" : "none",
      });
      if (expanded) frames[1].style.visibility = "visible";
      else
        hideTimer = setTimeout(() => {
          if (!expanded) frames[1].style.visibility = "hidden";
        }, 190);
      Object.assign(frames[2].style, {
        left: `${Math.max(0, Math.min(innerWidth - 364, x - 280))}px`,
        top: `${Math.max(0, y >= 300 ? y - 294 : Math.min(innerHeight - 288, y + 80))}px`,
        width: "364px",
        height: "288px",
        visibility: card ? "visible" : "hidden",
        pointerEvents: card ? "auto" : "none",
      });
    }
    function tell() {
      frames.forEach((f) =>
        f.contentWindow?.postMessage({ type: "geometry", expanded, card }, "*"),
      );
    }
    let shield: HTMLDivElement | undefined;
    function dragFrom(sx: number, sy: number) {
      if (shield) return;
      shield = document.createElement("div");
      shield.style.cssText =
        "position:fixed;inset:0;pointer-events:auto;cursor:grabbing;touch-action:none;background:transparent;";
      shadow.append(shield);
      const end = () => {
        shield?.remove();
        shield = undefined;
        void chrome.storage.local.set({ position: { x, y } });
        window.removeEventListener("blur", end);
      };
      shield.onpointermove = (event) => {
        if (!event.buttons) {
          end();
          return;
        }
        x += event.screenX - sx;
        y += event.screenY - sy;
        sx = event.screenX;
        sy = event.screenY;
        layout();
      };
      shield.onpointerup = shield.onpointercancel = end;
      window.addEventListener("blur", end, { once: true });
    }
    window.addEventListener("message", (event) => {
      if (
        !frames.some((f) => event.source === f.contentWindow) ||
        event.origin !== chrome.runtime.getURL("").slice(0, -1)
      )
        return;
      const m = event.data;
      if (m?.type === "toggle") {
        expanded = !expanded;
        if (!expanded) card = false;
        layout();
        tell();
      }
      if (m?.type === "card") {
        card = !!m.open;
        layout();
        tell();
      }
      if (
        m?.type === "drag" &&
        Number.isFinite(m.dx) &&
        Number.isFinite(m.dy) &&
        Math.abs(m.dx) < 2000 &&
        Math.abs(m.dy) < 2000
      ) {
        x += m.dx;
        y += m.dy;
        layout();
      }
      if (m?.type === "drop")
        void chrome.storage.local.set({ position: { x, y } });
      if (
        m?.type === "drag-start" &&
        Number.isFinite(m.screenX) &&
        Number.isFinite(m.screenY)
      )
        dragFrom(m.screenX, m.screenY);
      if (m?.type === "ready") {
        layout();
        tell();
      }
    });
    window.addEventListener("resize", layout);
    layout();
  });
}
