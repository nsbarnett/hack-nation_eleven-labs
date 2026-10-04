import { offline, validSnapshot, type Snapshot, type Action } from "./protocol";
const surface = location.hash.slice(1),
  root = document.getElementById("root")!;
const tell = (value: unknown) => parent.postMessage(value, "*");
let snapshot: Snapshot = { ...offline },
  port: chrome.runtime.Port,
  expanded = false;
let pending = false,
  lastQuestion = "",
  error = "",
  pendingId = "";
const svg = (paths: string) =>
  `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths}</svg>`;
const waveform = svg('<path d="M4 10v4m4-8v12m4-15v18m4-15v12m4-8v4"/>');
const icons = {
  record: svg(
    '<circle class="record-dot" cx="12" cy="12" r="6" fill="currentColor" stroke="none"/><rect class="stop-square" x="6" y="6" width="12" height="12" rx="2" fill="currentColor" stroke="none"/>',
  ),
  context: svg('<path d="M14 3H6v18h12V7zM14 3v5h4M9 12h6m-6 4h6"/>'),
  voice: svg(
    '<rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5 11v1a7 7 0 0 0 14 0v-1M12 19v3m-3 0h6"/>',
  ),
  mute: svg('<path d="M11 5 6 9H3v6h3l5 4zM16 9l5 6m0-6-5 6"/>'),
  open: svg('<path d="M14 3h7v7m0-7-11 11M9 3H3v18h18v-6"/>'),
};
function connect() {
  port = chrome.runtime.connect({ name: "surface" });
  port.onDisconnect.addListener(() => {
    snapshot = { ...offline };
    update();
    setTimeout(connect, 2000);
  });
  port.onMessage.addListener((message) => {
    if (message.type === "snapshot" && validSnapshot(message.value)) {
      snapshot = message.value;
      if (snapshot.question?.id && snapshot.question.id !== lastQuestion) {
        lastQuestion = snapshot.question.id;
        if (surface === "card") tell({ type: "card", open: true });
      }
    }
    if (message.type === "result" && message.id === pendingId) {
      pending = false;
      error = message.error || "";
      if (!error) {
        const input = root.querySelector("textarea");
        if (input) input.value = "";
      }
    }
    update();
  });
}
function command(action: Action["action"], text?: string) {
  if (pending && action !== "open") return;
  const value: Action = {
    type: "command",
    id: crypto.randomUUID(),
    epoch: snapshot.epoch,
    session: snapshot.session,
    question: snapshot.question?.id || null,
    action,
    text,
  };
  pending = action !== "open";
  pendingId = value.id;
  error = "";
  port.postMessage(value);
  update();
  // A missing reply is not replayed: reconnect with a snapshot and let the user retry.
  setTimeout(() => {
    if (pending && pendingId === value.id) {
      pending = false;
      error = "No response. Open Apprentice to check the connection.";
      update();
    }
  }, 12000);
}
if (surface === "orb") {
  root.innerHTML = `<button class="orb" aria-label="Toggle assistant controls" aria-expanded="false"><span class="wave">${waveform}</span><i></i></button>`;
  const button = root.querySelector("button")!;
  let down:
    | { x: number; y: number; lastX: number; lastY: number; moved: boolean }
    | undefined;
  button.onpointerdown = (e) => {
    down = {
      x: e.screenX,
      y: e.screenY,
      lastX: e.screenX,
      lastY: e.screenY,
      moved: false,
    };
    button.setPointerCapture(e.pointerId);
  };
  button.onpointermove = (e) => {
    if (!e.buttons) {
      down = undefined;
      return;
    }
    if (
      !down ||
      down.moved ||
      Math.hypot(e.screenX - down.x, e.screenY - down.y) <= 6
    )
      return;
    down.moved = true;
    tell({ type: "drag", dx: e.screenX - down.x, dy: e.screenY - down.y });
    button.releasePointerCapture(e.pointerId);
    // Continue the gesture on a temporary host-page shield. Moving an iframe
    // under pointer capture otherwise loses events in Chromium on Windows.
    tell({ type: "drag-start", screenX: e.screenX, screenY: e.screenY });
  };
  button.onpointerup = () => {
    if (down?.moved) tell({ type: "drop" });
    else tell({ type: "toggle" });
    down = undefined;
  };
  button.onpointercancel = () => {
    down = undefined;
  };
  button.onclick = (e) => {
    if (e.detail === 0) tell({ type: "toggle" });
  };
  button.onkeydown = (e) => {
    if (
      e.altKey &&
      ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)
    ) {
      e.preventDefault();
      tell({
        type: "drag",
        dx: e.key === "ArrowLeft" ? -10 : e.key === "ArrowRight" ? 10 : 0,
        dy: e.key === "ArrowUp" ? -10 : e.key === "ArrowDown" ? 10 : 0,
      });
      tell({ type: "drop" });
    }
    if (e.key === "Escape" && expanded) tell({ type: "toggle" });
  };
} else if (surface === "bar") {
  root.innerHTML =
    '<div class="bar">' +
    Object.entries(icons)
      .map(
        ([action, icon]) =>
          `<button data-action="${action}" aria-label="${action}"><span>${icon}</span><small>${action}</small></button>`,
      )
      .join("") +
    '</div><div class="status"></div>';
  root.querySelectorAll<HTMLButtonElement>("[data-action]").forEach(
    (button) =>
      (button.onclick = () => {
        const action = button.dataset.action as Action["action"];
        if (action === "context") tell({ type: "card", open: true });
        else command(action);
      }),
  );
} else {
  root.innerHTML =
    '<div class="card"><header><strong>Apprentice</strong><button aria-label="Close question">×</button></header><p class="question"></p><p class="status"></p><textarea aria-label="Context or answer" placeholder="Add context or answer…" maxlength="12000"></textarea><div class="actions"><button class="send">Send</button><button class="voice">Answer by voice</button><button class="defer">Defer</button></div><p class="error" role="status"></p></div>';
  root
    .querySelector("header button")!
    .addEventListener("click", () => tell({ type: "card", open: false }));
  root.querySelector(".send")!.addEventListener("click", () => {
    const input = root.querySelector("textarea")!;
    if (input.value.trim()) {
      command("context", input.value.trim());
    }
  });
  root
    .querySelector(".voice")!
    .addEventListener("click", () => command("voice"));
  root
    .querySelector(".defer")!
    .addEventListener("click", () => command("defer"));
}
function update() {
  root.classList.toggle("expanded", expanded);
  root.classList.toggle("recording", snapshot.recording === "recording");
  root.classList.toggle("capturing", snapshot.recording !== "idle");
  root.classList.toggle("listening", snapshot.voice === "listening");
  root.classList.toggle("speaking", snapshot.voice === "speaking");
  root.classList.toggle("muted", snapshot.muted);
  root.querySelector(".orb")?.setAttribute("aria-expanded", String(expanded));
  const status = !snapshot.connected
    ? "Disconnected · Open Apprentice"
    : snapshot.recording === "recording"
      ? "Recording locally · Privacy review pending"
      : snapshot.privacy !== "approved"
        ? "Privacy review pending"
        : "Reviewed recording";
  const label = root.querySelector(".status");
  if (label) label.textContent = error || status;
  const question = root.querySelector(".question");
  if (question)
    question.textContent =
      snapshot.question?.text || "Add context to your current workflow.";
  const errorLabel = root.querySelector(".error");
  if (errorLabel) errorLabel.textContent = error;
  root
    .querySelectorAll<HTMLButtonElement>("[data-action]")
    .forEach((button) => {
      const action = button.dataset.action!;
      const name =
        action === "record"
          ? snapshot.recording === "idle"
            ? "Record"
            : "Stop"
          : action === "mute"
            ? snapshot.muted
              ? "Unmute"
              : "Mute"
            : action === "open"
              ? "Open App"
              : action[0].toUpperCase() + action.slice(1);
      button.setAttribute("aria-label", name);
      button.querySelector("small")!.textContent = name;
      button.disabled = action !== "open" && (pending || !snapshot.connected);
    });
  root
    .querySelectorAll<HTMLButtonElement>(".actions button")
    .forEach(
      (button) =>
        (button.disabled = pending || !snapshot.connected || !snapshot.session),
    );
}
window.addEventListener("message", (event) => {
  if (event.source !== parent || event.data?.type !== "geometry") return;
  expanded = !!event.data.expanded;
  update();
});
tell({ type: "ready" });
connect();
update();
window.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && surface !== "orb")
    tell(
      surface === "card" ? { type: "card", open: false } : { type: "toggle" },
    );
});
