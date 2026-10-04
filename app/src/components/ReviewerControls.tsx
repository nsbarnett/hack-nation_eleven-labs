import { useState } from "react";
import { useApp, useMedia } from "../stores";
import { cancelVoice } from "../media";
import { Button, Toggle } from "./Controls";

export function ReviewerControls() {
  const data = useApp((s) => s.data)!;
  const [busy, setBusy] = useState(false);
  const saved = data.session?.reviewer || { enabled: false, presentation: "text" as const };
  const [pending, setPending] = useState<typeof saved | null>(null);
  const prefs = pending || saved;
  const voice = useMedia((s) => s.status.voice);
  async function update(patch: Partial<typeof prefs>) {
    const next = { ...prefs, ...patch };
    setPending(next);
    setBusy(true);
    cancelVoice();
    try {
      await useApp.getState().command("reviewer", next);
      useMedia.setState((s) => ({ status: { ...s.status, muted: next.presentation === "text" } }));
    } catch { /* command reports the error */ }
    finally { setPending(null); setBusy(false); }
  }
  return <section className="panel reviewer-controls" aria-label="Reviewer interjections">
    <Toggle label="Allow reviewer interjections" checked={prefs.enabled} disabled={busy || !data.session}
      onChange={(enabled) => void update({ enabled })} />
    <p className="small muted">The reviewer uses process scores and missing explanations to ask about meaningful actions. You can answer or choose Later.</p>
    <p className="small muted">During recording, questions use your typed and voice notes. Screen actions are analyzed after you approve the recording.</p>
    {prefs.enabled && !data.session?.evidence.some((e) => e.text && !e.kind.startsWith("trainee")) && <p role="status">Waiting for context or a note. Explain what you are doing using Send note or Voice; screen recording alone cannot trigger live questions before privacy approval.</p>}
    {prefs.enabled && voice === "idle" && !!data.session?.evidence.some((e) => e.text) && !data.busy.length && !data.question && <p className="small" role="status">The reviewer asks when your notes reveal a sufficiently important missing explanation. If a question was deferred or asked recently, it waits; you can continue in Debrief.</p>}
    <p className="small">Process evidence completeness: {data.evaluation?.process_score == null ? "Awaiting evidence" : `${data.evaluation.process_score}%`}. This measures captured explanations, not your performance.</p>
    {prefs.enabled && <fieldset disabled={busy} className="reviewer-modes"><legend>Question presentation</legend>
      {([["text", "Text only"], ["voice", "Voice only"], ["both", "Text and voice"]] as const).map(([value, label]) =>
        <label key={value}><input type="radio" name="reviewer-presentation" value={value} checked={prefs.presentation === value}
          onChange={() => void update({ presentation: value })} /> {label}</label>)}
    </fieldset>}
    {prefs.enabled && prefs.presentation !== "text" && !data.credentials.elevenlabs &&
      <p role="status">Voice is unavailable. Questions remain available as text until the app owner connects ElevenLabs.</p>}
    {prefs.enabled && !data.credentials.openai && <p role="status">The reviewer connection is unavailable. Your notes are saved; the app owner can reconnect the AI provider in Settings.</p>}
    {prefs.enabled && data.recording === "recording" && !!data.evaluation?.dimensions.answer_sufficiency.pending_evidence && !data.busy.length &&
      <Button disabled={voice !== "idle" || !data.credentials.openai} onClick={() => void useApp.getState().command("reviewer-tick", { retry: true, available: true, duration: useMedia.getState().status.duration }).catch(() => {})}>Review saved notes</Button>}
  </section>;
}
