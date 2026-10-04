import "./platform";
import { installExtensionBridge } from "./web/extensionBridge";
import React from "react";
import { createRoot } from "react-dom/client";
import { MotionConfig } from "motion/react";
import { Tooltip } from "radix-ui";
import { App } from "./App";
import { FloatingAssistant } from "./components/FloatingAssistant";
import { useApp, useMedia, report } from "./stores";
import { cancelVoice, speak } from "./media";
import "./style.css";
installExtensionBridge();
for (const event of ["keydown", "pointerdown", "input"]) {
  window.addEventListener(event, () => useMedia.setState({ lastInteractionAt: Date.now() }), { passive: true });
}
const overlay = location.hash === "#overlay";
let spoken = "";
let refreshTimer: ReturnType<typeof setTimeout> | undefined;
void useApp.getState().refresh();
window.desktop.onEvent((event) => {
  if (event.type === "media") {
    useMedia.setState({ status: event.media });
    return;
  }
  if (event.type === "error" || event.type === "backend-offline")
    report(event.message);
  if (["state", "resync", "error"].includes(event.type)) {
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(() => void useApp.getState().refresh(), 50);
  }
});
if (!overlay)
  useApp.subscribe((state, previous) => {
    const question = state.data?.question;
    if (
      state.data?.session?.id !== previous.data?.session?.id ||
      (!question && previous.data?.question) ||
      (previous.data?.cloud && !state.data?.cloud)
    )
      cancelVoice();
    if (window.desktop.platform !== "web" && question && question.id !== spoken) {
      spoken = question.id;
      void speak(question.text);
    }
  });
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <MotionConfig reducedMotion="user">
      <Tooltip.Provider delayDuration={350}>
        {overlay ? <FloatingAssistant /> : <App />}
      </Tooltip.Provider>
    </MotionConfig>
  </React.StrictMode>,
);
