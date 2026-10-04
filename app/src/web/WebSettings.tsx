import { useState } from "react";
import { KeyRound, ShieldCheck, Trash2 } from "lucide-react";
import { useApp, useMedia } from "../stores";
import { Button, Modal } from "../components/Controls";

export function WebSettings() {
  const data = useApp((s) => s.data)!;
  const recording = useMedia((s) => s.status.state);
  const [pendingDelete, setPendingDelete] = useState<{ id: string; title: string } | null>(null);
  const [confirmation, setConfirmation] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const canDelete = !!pendingDelete && pendingDelete.id === data.session?.id
    && recording === "idle" && confirmation === "confirm delete" && !deleting;

  function closeDelete() {
    if (deleting) return;
    setPendingDelete(null);
    setConfirmation("");
    setDeleteError("");
  }

  async function deleteWorkflow() {
    if (!canDelete) return;
    setDeleting(true);
    setDeleteError("");
    try {
      await useApp.getState().command("delete-session", {
        confirmation,
        expectedSessionId: pendingDelete!.id,
      });
      setPendingDelete(null);
      setConfirmation("");
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : String(error));
    } finally {
      setDeleting(false);
    }
  }
  return <>
    <header className="page-heading compact"><span className="eyebrow">YOUR WORKSPACE</span><h1>Connections & privacy</h1><p>A private browser workspace for capturing and teaching real work.</p></header>
    <div className="settings-layout">
      <section className="panel settings-section">
        <h2><KeyRound size={20} /> Hosted connections</h2>
        <p>AI and voice connections are provided by the app owner. You do not need API keys.</p>
        <p>OpenAI <span className="badge">{data.credentials.openai ? "Configured" : "Unavailable — contact the app owner"}</span></p>
        <p>ElevenLabs <span className="badge">{data.credentials.elevenlabs ? "Configured" : "Unavailable — text answers still work"}</span></p>
        <p className="muted">Connection status reflects server configuration. Provider errors will appear when a request cannot be completed. The hosted allowance is {data.limits?.dailyAiCalls} AI or voice requests per browser per day, subject to the app's shared daily limit.</p>
      </section>
      <section className="panel settings-section">
        <h2><ShieldCheck size={20} /> Your data</h2>
        <p>Video and screenshots stay in this browser's storage. Clearing site data or changing browser removes access to that media. Export recordings you want to keep.</p>
        <p>Notes, observations, conversation text, and Work Maps are saved online in this guest workspace. Inactive workflows are deleted after seven days. No account or cross-device access is provided.</p>
        <p>Original media and English OCR stay in this browser. After you review and explicitly approve a rendered copy, selected redacted frames can be sent to OpenAI. The server briefly holds up to three frames in memory; it does not save image files. Typed notes are saved online. Voice notes go to ElevenLabs only when you start the microphone; visual covers do not redact speech.</p>
        <p>Pause stops capture and microphone tracks. Deleting saved evidence cannot recall information already sent to a provider.</p>
        <Button className="danger" disabled={!data.session || recording !== "idle"} onClick={() => {
          if (!data.session) return;
          setConfirmation("");
          setDeleteError("");
          setPendingDelete({ id: data.session.id, title: data.session.title });
        }}><Trash2 size={16} /> Delete open workflow & media</Button>
      </section>
      <section className="panel settings-section">
        <h2>Floating browser assistant</h2>
        <p>Use the companion in Chrome or Edge to control this open workspace from other websites. It cannot float over other desktop applications.</p>
        <a className="button" href="/downloads/apprentice-extension.zip" download>Download extension ZIP</a>
        <ol><li>Extract the ZIP into a folder.</li><li>Open chrome://extensions or edge://extensions, enable Developer mode, then choose Load unpacked.</li><li>Select the extracted folder and open its extension options.</li><li>Set the Apprentice origin to <code>{location.origin}</code> and grant website access.</li><li>Reload this tab and the websites where you want the orb.</li></ol>
        <p>The orb stays in place as controls expand. Drag it, or focus it and use Alt + arrow keys. Recording and microphone permission prompts remain in this app tab.</p>
      </section>
    </div>
    <p className="small muted">AI Apprentice {data.version} · Browser edition · Chrome or Edge recommended</p>
    <Modal open={!!pendingDelete} onChange={(open) => { if (!open) closeDelete(); }}
      title="Delete workflow and data?"
      description={`This permanently deletes “${pendingDelete?.title ?? ""}”, its hosted notes, conversation, Work Map, and media stored in this browser. This cannot be undone.`}>
      <form onSubmit={(event) => { event.preventDefault(); void deleteWorkflow(); }}>
        <label className="field">
          Type confirm delete to continue
          <input value={confirmation} onChange={(event) => setConfirmation(event.target.value)}
            autoComplete="off" autoCapitalize="none" spellCheck={false} disabled={deleting} />
        </label>
        {pendingDelete && pendingDelete.id !== data.session?.id && <p role="alert">The open workflow changed. Close this dialog and try again.</p>}
        {deleteError && <p role="alert">{deleteError}</p>}
        <div className="button-row">
          <Button type="button" disabled={deleting} onClick={closeDelete}>Cancel</Button>
          <Button type="submit" className="danger" disabled={!canDelete}>{deleting ? "Deleting…" : "Delete permanently"}</Button>
        </div>
      </form>
    </Modal>
  </>;
}
