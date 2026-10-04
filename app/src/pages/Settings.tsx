import { useState } from "react";
import { KeyRound, FolderInput, ShieldCheck, Check } from "lucide-react";
import { useApp, run } from "../stores";
import { Button } from "../components/Controls";
export function Settings() {
  const data = useApp((s) => s.data)!;
  const [openai, setOpenai] = useState(""),
    [eleven, setEleven] = useState(""),
    [voice, setVoice] = useState(data.credentials.voiceId),
    [model, setModel] = useState(data.credentials.model),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  async function save() {
    setBusy(true);
    try {
      const patch: Record<string, string> = { voice_id: voice, model };
      if (openai.trim()) patch.openai_key = openai.trim();
      if (eleven.trim()) patch.eleven_key = eleven.trim();
      await window.desktop.saveCredentials(patch);
      setOpenai("");
      setEleven("");
      await useApp.getState().refresh();
      setMessage("Settings saved securely.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <header className="page-heading compact">
        <span className="eyebrow">MAKE APPRENTICE YOURS</span>
        <h1>Settings</h1>
        <p>Connections, local data, and the boundaries of your assistant.</p>
      </header>
      <div className="settings-layout">
        <section className="panel settings-section">
          <h2>
            <KeyRound size={20} />
            AI connections
          </h2>
          <p className="muted">
            Keys are encrypted using your operating system. They are never
            included in recordings or exports.
          </p>
          <label className="field">
            OpenAI API key{" "}
            <span className="badge">
              {data.credentials.openai ? "Configured" : "Not configured"}
            </span>
            <input
              type="password"
              autoComplete="off"
              value={openai}
              onChange={(e) => setOpenai(e.target.value)}
              placeholder="Enter a key to add or replace it"
            />
          </label>
          <div className="button-row">
            <Button
              disabled={!data.credentials.openai}
              onClick={() =>
                run(async () => {
                  await window.desktop.checkCredentials("openai");
                  setMessage("OpenAI connection verified.");
                })
              }
            >
              Check connection
            </Button>
            <Button
              disabled={!data.credentials.openai}
              onClick={() =>
                run(async () => {
                  await window.desktop.saveCredentials({ openai_key: "" });
                  await useApp.getState().refresh();
                })
              }
            >
              Remove key
            </Button>
          </div>
          <label className="field">
            Vision & reasoning model
            <input value={model} onChange={(e) => setModel(e.target.value)} />
          </label>
          <hr />
          <label className="field">
            ElevenLabs API key{" "}
            <span className="badge">
              {data.credentials.elevenlabs ? "Configured" : "Not configured"}
            </span>
            <input
              type="password"
              autoComplete="off"
              value={eleven}
              onChange={(e) => setEleven(e.target.value)}
              placeholder="Enter a key to add or replace it"
            />
          </label>
          <div className="button-row">
            <Button
              disabled={!data.credentials.elevenlabs}
              onClick={() =>
                run(async () => {
                  await window.desktop.checkCredentials("elevenlabs");
                  setMessage("ElevenLabs connection verified.");
                })
              }
            >
              Check connection
            </Button>
            <Button
              disabled={!data.credentials.elevenlabs}
              onClick={() =>
                run(async () => {
                  await window.desktop.saveCredentials({ eleven_key: "" });
                  await useApp.getState().refresh();
                })
              }
            >
              Remove key
            </Button>
          </div>
          <label className="field">
            ElevenLabs voice ID
            <input value={voice} onChange={(e) => setVoice(e.target.value)} />
          </label>
          <Button
            className="primary"
            disabled={busy || !model.trim() || !voice.trim()}
            onClick={() => run(save)}
          >
            Save settings
          </Button>
          {message && (
            <p className="success" role="status">
              <Check size={15} />
              {message}
            </p>
          )}
        </section>
        <div>
          <section className="panel settings-section">
            <h2>
              <ShieldCheck size={20} />
              Your recording boundaries
            </h2>
            <p>
              Recordings and evidence stay on this computer. Cloud analysis
              shares sampled screens and relevant context with OpenAI only when
              enabled.
            </p>
            <p>
              Voice sends your explicit microphone answer to ElevenLabs for
              transcription. Spoken questions are synthesized through
              ElevenLabs.
            </p>
            <p>
              Pause stops capture and microphone tracks. Previously sent
              provider requests cannot be recalled.
            </p>
            <p>
              No system audio, automatic external actions, or background
              microphone listening.
            </p>
          </section>
          <section className="panel settings-section">
            <h2>
              <FolderInput size={20} />
              Bring your existing work
            </h2>
            <p>
              Import live sessions from the previous application. Original files
              stay untouched; demo sessions are excluded.
            </p>
            <Button
              onClick={() =>
                run(async () => {
                  const result = await window.desktop.importLegacy();
                  await useApp.getState().refresh();
                  setMessage(`Imported ${result.count} live sessions.`);
                })
              }
            >
              Import legacy recordings
            </Button>
          </section>
          <p className="small muted">
            AI Apprentice {data.version} · Electron desktop
          </p>
        </div>
      </div>
    </>
  );
}
