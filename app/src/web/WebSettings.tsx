import { KeyRound, ShieldCheck, Trash2 } from "lucide-react";
import { useApp, useMedia, run } from "../stores";
import { Button } from "../components/Controls";

export function WebSettings() {
  const data = useApp((s) => s.data)!;
  const recording = useMedia((s) => s.status.state);
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
        <p>When you enable cloud analysis, selected screenshots and context are sent to OpenAI through the server. The server briefly holds up to three frames in memory; it does not save image files. Voice answers are sent to ElevenLabs only when you start the microphone.</p>
        <p>Pause stops capture and microphone tracks. Deleting saved evidence cannot recall information already sent to a provider.</p>
        <Button className="danger" disabled={!data.session || recording !== "idle"} onClick={() => run(() => useApp.getState().command("delete-session"))}><Trash2 size={16} /> Delete open workflow & media</Button>
      </section>
    </div>
    <p className="small muted">AI Apprentice {data.version} · Browser edition · Chrome or Edge recommended</p>
  </>;
}
