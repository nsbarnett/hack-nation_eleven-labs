import { useState, useEffect } from "react";
import {
  Library as LibraryIcon,
  Image,
  FileText,
  Video,
  Trash2,
} from "lucide-react";
import { useApp, run } from "../stores";
import { Button, Empty, Modal, IconButton } from "../components/Controls";
export function Library() {
  const session = useApp((s) => s.data?.session);
  const [image, setImage] = useState<string | null>(null);
  const [video, setVideo] = useState<string | null>(null);
  useEffect(() => () => { if (image?.startsWith("blob:")) URL.revokeObjectURL(image); }, [image]);
  useEffect(() => () => { if (video?.startsWith("blob:")) URL.revokeObjectURL(video); }, [video]);
  const [reference, setReference] = useState("");
  if (!session)
    return (
      <Empty icon={<LibraryIcon size={30} />} heading="Your evidence library">
        Open a workflow to explore its notes, references, screenshots, and
        recordings.
      </Empty>
    );
  return (
    <>
      <header className="page-heading compact">
        <span className="eyebrow">THE SOURCE OF WHAT YOU KNOW</span>
        <h1>Evidence library</h1>
        <p>
          {session.title} · {session.evidence.length} sources
        </p>
      </header>
      <section className="panel reference-form">
        <h3>Add reference context</h3>
        <textarea
          aria-label="Reference text"
          value={reference}
          onChange={(e) => setReference(e.target.value)}
          placeholder="Paste relevant reference text and identify its source…"
        />
        <Button
          disabled={!reference.trim()}
          onClick={() =>
            run(async () => {
              await useApp
                .getState()
                .command("note", { kind: "reference", text: reference });
              setReference("");
            })
          }
        >
          Save reference
        </Button>
      </section>
      <div className="section-heading">
        <h2>Recordings</h2>
      </div>
      {window.desktop.platform === "web" && <p className="muted small">Media is stored only in the browser where it was captured. Use the video player's download control to keep a copy.</p>}
      {session.recordings.map((file) => (
        <button
          className="panel media-row"
          key={file}
          onClick={() => run(async () => { const url = await window.desktop.media(file); if (url) setVideo(url); })}
        >
          <Video size={18} />
          <span>{file}</span>
          <span className="small muted">Open video</span>
        </button>
      ))}
      {!session.recordings.length && (
        <p className="muted">No completed recording segments.</p>
      )}
      <div className="section-heading">
        <h2>Notes & screenshots</h2>
      </div>
      <div className="panel">
        {session.evidence.map((e) => (
          <div className="evidence-row" key={e.id}>
            {e.image ? <Image size={18} /> : <FileText size={18} />}
            <button
              className="evidence-text"
              onClick={() =>
                e.image
                  ? run(async () =>
                      setImage(await window.desktop.media(e.image)),
                    )
                  : undefined
              }
            >
              <strong>
                {e.kind.replaceAll("_", " ")} · {Math.floor(e.timestamp)}s
              </strong>
              <span>{e.text || `Source ${e.id.slice(0, 8)}`}</span>
              {e.question && <small>{e.question}</small>}
            </button>
            <IconButton
              label="Forget evidence"
              onClick={() =>
                run(() => useApp.getState().command("forget", { id: e.id }))
              }
            >
              <Trash2 size={15} />
            </IconButton>
          </div>
        ))}
        {!session.evidence.length && (
          <Empty heading="No evidence yet">
            Record your task or add context to begin.
          </Empty>
        )}
      </div>
      <Modal
        open={!!video}
        onChange={() => setVideo(null)}
        title="Local recording"
        description="This recording is stored in this browser."
      >
        {video && <><video className="evidence-image" src={video} controls /><a href={video} download="apprentice-recording.webm">Download recording</a></>}
      </Modal>
      <Modal
        open={!!image}
        onChange={() => setImage(null)}
        title="Recorded evidence"
        description="A locally saved screenshot from this session."
      >
        {image && (
          <img
            className="evidence-image"
            src={image}
            alt="Session screenshot"
          />
        )}
      </Modal>
    </>
  );
}
