import { useState } from "react";
import { Monitor, Check } from "lucide-react";
import { Modal, Button, Toggle } from "./Controls";
import { useApp, report } from "../stores";
import { startRecording } from "../media";
import type { Source } from "../types";
export function RecordingSetup({
  open,
  onChange,
  newWorkflow = true,
}: {
  open: boolean;
  onChange: (value: boolean) => void;
  newWorkflow?: boolean;
}) {
  const [title, setTitle] = useState(""),
    [context, setContext] = useState(""),
    [cloud, setCloud] = useState(false),
    [sources, setSources] = useState<Source[]>([]),
    [source, setSource] = useState<Source | null>(null),
    [busy, setBusy] = useState(false),
    [issue, setIssue] = useState("");
  async function loadSources() {
    try {
      setSources(await window.desktop.sources());
    } catch (error) {
      report(error);
    }
  }
  async function begin() {
    setBusy(true);
    setIssue("");
    let captured: MediaStream | undefined;
    try {
      if (window.desktop.platform === "web") {
        if (!navigator.mediaDevices?.getDisplayMedia) throw new Error("Screen sharing requires Chrome or Edge on a desktop computer.");
        captured = await navigator.mediaDevices.getDisplayMedia({ video: { frameRate: 15 }, audio: false });
      } else if (!source) throw new Error("Choose a screen or window.");
      if (newWorkflow)
        await useApp.getState().command("new", { title, context, cloud });
      await startRecording(source || undefined, captured);
      useApp.getState().go("Record");
      onChange(false);
    } catch (error) {
      captured?.getTracks().forEach((track) => track.stop());
      setIssue(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      open={open}
      onChange={onChange}
      title={newWorkflow ? "Record a workflow" : "Choose what to capture"}
      description={window.desktop.platform === "web" ? "Video and screenshots stay in this browser. Notes and Work Maps are saved online for seven days. Screen analysis waits until you review, redact, and approve the recording. Typed notes are saved online; voice notes use ElevenLabs when you choose Voice." : "Your recording stays on this computer. Choose whether to share sampled screens with AI."}
    >
      {newWorkflow && (
        <>
          <label className="field">
            Workflow title
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={200}
              autoFocus
              placeholder="Name the task you are documenting"
            />
          </label>
          <label className="field">
            Context
            <textarea
              value={context}
              onChange={(e) => setContext(e.target.value)}
              placeholder="What are you doing, and what should the apprentice learn?"
            />
          </label>
          <Toggle
            label="Enable cloud analysis for this session"
            checked={cloud}
            onChange={setCloud}
          />
        </>
      )}
      {window.desktop.platform !== "web" && <><div className="section-heading">
        <h3>Screen or window</h3>
        <Button onClick={() => void loadSources()}>
          <Monitor size={15} />
          Choose source
        </Button>
      </div>
      <div className="source-grid">
        {sources.map((item) => (
          <button
            key={item.id}
            className={`source ${source?.id === item.id ? "selected" : ""}`}
            onClick={() => setSource(item)}
          >
            <img src={item.thumbnail} alt="" />
            <span>
              {item.name}
              {source?.id === item.id && <Check size={15} />}
            </span>
          </button>
        ))}
      </div>
      </>}
      <p className="muted small">
        {window.desktop.platform === "web" ? "The browser will ask you to choose a screen or window. Keep this tab open. Capture is limited to five minutes and 100 MB per workflow." : "Screen and microphone permissions are managed by your operating system."} System audio is not recorded.
      </p>
      {issue && <p className="error-banner" role="alert">{issue}</p>}
      <Button
        className="primary full"
        disabled={busy || (window.desktop.platform !== "web" && !source) || (newWorkflow && !title.trim())}
        onClick={() => void begin()}
      >
        {busy ? "Starting…" : "Start recording"}
      </Button>
    </Modal>
  );
}
