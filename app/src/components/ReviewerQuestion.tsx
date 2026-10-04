import { useEffect, useRef, useState } from "react";
import { MessageCircle, Mic, Volume2 } from "lucide-react";
import { useApp, useMedia, run } from "../stores";
import { cancelVoice, speak, voiceNote } from "../media";
import { Button } from "./Controls";

export function ReviewerQuestion() {
  const data = useApp((s) => s.data)!;
  const status = useMedia((s) => s.status);
  const [answer, setAnswer] = useState(""), [saving, setSaving] = useState(false);
  const [fallback, setFallback] = useState(false), [transcript, setTranscript] = useState(false);
  const attempted = useRef(new Set<string>());
  const q = data.question, prefs = data.session?.reviewer;
  const live = q?.phase === "live";
  const visible = !!q && (!live || (!!prefs?.enabled && status.state === "recording"));
  const mode = prefs?.presentation || "text";
  const owner = data.session?.id;
  useEffect(() => {
    setAnswer(""); setFallback(false); setTranscript(false);
    return () => cancelVoice();
  }, [q?.id, owner]);
  useEffect(() => {
    if (!visible || mode === "text" || status.muted) { cancelVoice(); return; }
    let active = true;
    const play = () => {
      if (!q || attempted.current.has(q.id) || useMedia.getState().status.voice !== "idle") return;
      attempted.current.add(q.id);
      if (!data.credentials.elevenlabs) { setFallback(true); return; }
      void speak(q.text).then((ok) => { if (active && !ok) setFallback(true); });
    };
    const timer = setTimeout(play, 0);
    const unsubscribe = useMedia.subscribe(play);
    return () => { active = false; clearTimeout(timer); unsubscribe(); cancelVoice(); };
  }, [q?.id, visible, mode, status.muted, data.credentials.elevenlabs]);
  useEffect(() => {
    if ((!prefs?.enabled && live) || status.state === "paused") cancelVoice();
  }, [prefs?.enabled, live, status.state]);
  if (window.desktop.platform !== "web" || !visible || !q) return null;
  const showText = mode !== "voice" || fallback || transcript;
  async function submit() {
    if (!answer.trim() || saving) return;
    setSaving(true);
    try { await useApp.getState().command("note", { kind: "answer", text: answer, expectedQuestionId: q!.id }); }
    catch { /* command displays error and retains the answer */ }
    finally { setSaving(false); }
  }
  return <aside className="reviewer-question panel" aria-label="Reviewer question">
    <div className="section-heading"><strong><MessageCircle size={18} /> Reviewer question</strong>
      <span className="badge">Priority {q.priority_score ?? "—"}/100</span></div>
    {showText ? <p role="status">{q.text}</p> : <p role="status">{status.voice === "speaking" ? "The reviewer is speaking…" : status.voice === "thinking" ? "Preparing spoken question…" : "A spoken question is ready."}</p>}
    {fallback && <p className="small">Voice could not play. The question is shown above; you can retry audio.</p>}
    {mode === "voice" && !showText && <button className="text-button" onClick={() => setTranscript(true)}>Show question text</button>}
    <form onSubmit={(e) => { e.preventDefault(); void submit(); }}>
      <label className="field">Your explanation<input value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder="Explain your reasoning…" /></label>
      <div className="button-row">
        <Button disabled={!answer.trim() || saving}>{saving ? "Saving…" : "Send explanation"}</Button>
        <Button type="button" disabled={saving} onClick={() => run(voiceNote)}><Mic size={15} />{status.voice === "listening" ? "Finish answer" : "Voice answer"}</Button>
        {mode !== "text" && <Button type="button" disabled={!data.credentials.elevenlabs || status.voice === "listening"} onClick={() => {
          useMedia.setState((s) => ({ status: { ...s.status, muted: false } }));
          void speak(q.text).then((ok) => setFallback(!ok));
        }}><Volume2 size={15} /> Replay</Button>}
        <Button type="button" disabled={saving} onClick={() => run(() => useApp.getState().command("defer", { expectedQuestionId: q.id }))}>Later</Button>
      </div>
    </form>
    {!live && <button className="text-button" onClick={() => useApp.getState().go("Debrief")}>Open Debrief</button>}
  </aside>;
}
