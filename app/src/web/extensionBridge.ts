/** Only our configured origin receives extension commands. Replays and stale
 * question/session identities are rejected again at the application boundary. */
import { validAction, type Snapshot } from "../../extension/protocol";
import { useApp, useMedia } from "../stores";
import { stopRecording, toggleMute, voiceNote } from "../media";
let sequence = 0;
const epoch = crypto.randomUUID(),
  seen = new Set<string>();
export function installExtensionBridge() {
  if (window.desktop.platform !== "web") return;
  let connected = false;
  const send = (value: unknown) =>
    window.postMessage({ source: "apprentice-app", value }, location.origin);
  const snapshot = (): Snapshot => {
    const { data } = useApp.getState(),
      { status } = useMedia.getState();
    const question = data?.question;
    const visible = question && (question.phase !== "live" || (data?.session?.reviewer?.enabled && status.state === "recording"));
    return {
      connected: connected && !!data,
      epoch,
      sequence: ++sequence,
      session: data?.session?.id || null,
      question: visible
        ? { id: question.id, text: data?.session?.reviewer?.presentation === "voice" ? "A spoken reviewer question is ready. Open Apprentice to replay or view its text." : question.text }
        : null,
      recording: status.state,
      voice: status.voice,
      muted: status.muted,
      privacy: data?.session?.privacy.status || "pending",
      busy: !!data?.busy.length,
    };
  };
  const sync = () => send({ type: "snapshot", value: snapshot() });
  window.desktop.onEvent((event) => {
    if (event.type === "backend-offline") connected = false;
    if (event.type === "resync") connected = true;
    sync();
  });
  useApp.subscribe(sync);
  useMedia.subscribe(sync);
  window.addEventListener("message", (event) => {
    if (
      event.source !== window ||
      event.origin !== location.origin ||
      event.data?.source !== "apprentice-extension"
    )
      return;
    const value = event.data.value;
    if (value?.type === "snapshot-request") {
      sync();
      return;
    }
    if (!validAction(value) || seen.has(value.id)) return;
    seen.add(value.id);
    if (seen.size > 1000) seen.delete(seen.values().next().value!);
    void (async () => {
      const data = useApp.getState().data;
      if (
        value.epoch !== epoch ||
        value.session !== (data?.session?.id || null) ||
        value.question !== (data?.question?.id || null)
      )
        throw new Error(
          "The workflow or question changed. Reconnect before trying again.",
        );
      if (value.action === "mute") toggleMute();
      if (value.action === "record") {
        if (useMedia.getState().status.state !== "idle") await stopRecording();
        else await window.desktop.relay("record"); // Capture selection requires a click in the app tab.
      }
      if (value.action === "voice") {
        useApp.getState().go("Record");
        await voiceNote();
      }
      if (value.action === "context" && value.text?.trim())
        await useApp
          .getState()
          .command("note", {
            kind: value.question ? "answer" : "note",
            text: value.text,
            expectedQuestionId: value.question,
          });
      if (value.action === "defer")
        await useApp
          .getState()
          .command("defer", { expectedQuestionId: value.question });
    })()
      .then(
        () => send({ type: "result", id: value.id }),
        (error) =>
          send({
            type: "result",
            id: value.id,
            error: error instanceof Error ? error.message : "Action failed.",
          }),
      )
      .finally(sync);
  });
}
