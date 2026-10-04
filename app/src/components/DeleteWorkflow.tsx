import { useState } from "react";
import { create } from "zustand";
import { Trash2 } from "lucide-react";
import { useApp, useMedia } from "../stores";
import { Button, Modal } from "./Controls";

type Target = { id: string; title: string };
const useDeletion = create<{ target: Target | null }>(() => ({ target: null }));
export function DeleteWorkflow({ workflow }: { workflow: Target }) {
  const recording = useMedia((s) => s.status.state);
  const active = useApp((s) => s.data?.session?.id);
  const blocked = active === workflow.id && recording !== "idle";
  if (window.desktop.platform !== "web") return null;
  return <Button className="danger" disabled={blocked} title={blocked ? "Stop recording before deleting this workflow." : undefined} aria-label={`Delete ${workflow.title}`} onClick={() => useDeletion.setState({ target: workflow })}>
    <Trash2 size={16} /> Delete
  </Button>;
}

export function WorkflowDeletionDialog() {
  const workflow = useDeletion((s) => s.target);
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const recording = useMedia((s) => s.status.state);
  const active = useApp((s) => s.data?.session?.id);
  const blocked = active === workflow?.id && recording !== "idle";
  function close() { if (!busy) { useDeletion.setState({ target: null }); setError(""); } }
  async function remove() {
    if (!workflow || busy || blocked) return;
    if (error && useApp.getState().error === error) useApp.setState({ error: "" });
    setBusy(true); setError("");
    try {
      await useApp.getState().command("delete-session", { id: workflow.id, confirmed: true });
      useDeletion.setState({ target: null });
      useApp.setState({ notice: `Deleted “${workflow.title}” and its saved data.` });
    } catch (e) { setError(e instanceof Error ? e.message : "Deletion failed. Try again."); }
    finally { setBusy(false); }
  }
  return <>
    <Modal open={!!workflow} onChange={(value) => { if (!value) close(); }} title={`Delete “${workflow?.title || "workflow"}”?`}
      description="This permanently removes this workflow, its notes, questions, Work Map, and recordings stored in this browser. This cannot be undone.">
      {error && <p role="alert">{error}</p>}
      {blocked && <p>Stop recording before deleting this workflow.</p>}
      <div className="button-row">
        <Button disabled={busy} onClick={close}>Cancel</Button>
        <Button className="danger" disabled={busy || blocked} onClick={() => void remove()}>{busy ? "Deleting…" : "Delete workflow"}</Button>
      </div>
    </Modal>
  </>;
}
