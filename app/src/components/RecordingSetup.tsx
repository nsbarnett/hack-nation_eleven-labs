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
    [busy, setBusy] = useState(false);
  async function loadSources() {
    try {
      setSources(await window.desktop.sources());
    } catch (error) {
      report(error);
    }
  }
  async function begin() {
    setBusy(true);
    try {
      if (!source) throw new Error("Choose a screen or window.");
      if (newWorkflow)
        await useApp.getState().command("new", { title, context, cloud });
      await startRecording(source);
      useApp.getState().go("Record");
      onChange(false);
    } catch (error) {
      report(error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      open={open}
      onChange={onChange}
      title={newWorkflow ? "Record a workflow" : "Choose what to capture"}
      description="Your recording stays on this computer. Choose whether to share sampled screens with AI."
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
      <div className="section-heading">
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
      <p className="muted small">
        Screen and microphone permissions are managed by your operating system.
        System audio is not recorded.
      </p>
      <Button
        className="primary full"
        disabled={busy || !source || (newWorkflow && !title.trim())}
        onClick={() => void begin()}
      >
        {busy ? "Starting…" : "Start recording"}
      </Button>
    </Modal>
  );
}
