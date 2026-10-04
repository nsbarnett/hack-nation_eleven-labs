import { useState, useEffect, useRef } from "react";
import { AudioLines, ArrowUp, Mic, VolumeX, Volume2 } from "lucide-react";
import { useApp, useMedia, run } from "../stores";
import { voiceNote, toggleMute } from "../media";
import { Button, IconButton, Toggle } from "./Controls";
const states: Record<string, string> = {
  idle: "Ready when you are",
  watching: "Watching your screen",
  thinking: "Thinking…",
  waiting: "Waiting for a natural pause",
  detected: "Potential decision detected",
  question: "A question for you",
};
export function AssistantPanel() {
  const data = useApp((s) => s.data)!;
  const status = useMedia((s) => s.status);
  const [text, setText] = useState("");
  const end = useRef<HTMLDivElement>(null);
  const focusContext = useApp((s) => s.focusContext);
  useEffect(() => {
    if (focusContext) {
      document.getElementById("context-input")?.focus();
      useApp.setState({ focusContext: false });
    }
  }, [focusContext]);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [data.session?.messages.length]);
  async function submit() {
    if (!text.trim()) return;
    await useApp
      .getState()
      .command("note", { text, kind: data.question ? "answer" : "note", expectedQuestionId: data.question?.id || null });
    setText("");
  }
  return (
    <aside className="assistant-column">
      <section className="panel conversation">
        <div className="assistant-heading">
          <AudioLines size={23} />
          <div>
            <h3>AI Assistant</h3>
            <p>
              {status.voice === "idle"
                ? window.desktop.platform === "web"
                  ? data.busy.length ? "Processing context…" : data.question ? "A question for you" : status.state === "recording" ? "Recording locally · Add notes for the reviewer" : "Ready when you are"
                  : data.cloud
                  ? (window.desktop.platform === "web" && data.session?.privacy.status !== "approved" ? "Privacy review pending" : states[data.assistant] || data.assistant)
                  : "Cloud analysis is off"
                : status.voice}
            </p>
          </div>
          <IconButton
            label={status.muted ? "Unmute assistant" : "Mute assistant"}
            onClick={toggleMute}
          >
            {status.muted ? <VolumeX size={17} /> : <Volume2 size={17} />}
          </IconButton>
        </div>
        <div className="messages">
          {!data.session?.messages.length && (
            <p className="conversation-empty">
              Your notes and the apprentice’s questions will appear here as you
              work.
            </p>
          )}
          {data.session?.messages.map((message) => (
            <div key={message.id} className={`message ${message.role}`}>
              <span>
                {message.role === "assistant"
                  ? "Apprentice"
                  : message.role === "user"
                    ? "You"
                    : "Session"}
              </span>
              <p>{message.text}</p>
            </div>
          ))}
          <div ref={end} />
        </div>
        {data.question && (
          <div className="question-actions">
            <Button onClick={() => run(voiceNote)}>
              <Mic size={14} />
              Answer
            </Button>
            <Button
              onClick={() => document.getElementById("context-input")?.focus()}
            >
              Type instead
            </Button>
            <button
              className="text-button"
              onClick={() => run(() => useApp.getState().command("defer", { expectedQuestionId: data.question?.id }))}
            >
              Later
            </button>
          </div>
        )}
        <form
          className="composer"
          onSubmit={(e) => {
            e.preventDefault();
            run(submit);
          }}
        >
          <input
            id="context-input"
            aria-label="Add a note or answer"
            placeholder="Add a note or answer…"
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={!data.session || status.state === "paused"}
          />
          <IconButton
            type="button"
            label={
              status.voice === "listening" ? "Finish answer" : "Voice note"
            }
            disabled={!data.session}
            onClick={() => run(voiceNote)}
          >
            <Mic size={16} />
          </IconButton>
          <button
            className="send"
            aria-label="Send note"
            disabled={!text.trim() || !data.session}
          >
            <ArrowUp size={17} />
          </button>
        </form>
      </section>
      <section className="panel settings-card">
        <h3>About your assistant</h3>
        {window.desktop.platform !== "web" && status.state === "recording" && <Button disabled={!!data.question || !!data.busy.length || status.voice !== "idle"} onClick={() => run(() => useApp.getState().command("question-ready"))}>Ready for a question</Button>}
        {window.desktop.platform !== "web" && <Toggle
          label="Cloud analysis"
          checked={data.cloud}
          onChange={(enabled) =>
            run(() => useApp.getState().command("cloud", { enabled }))
          }
        />}
        <p className="small muted">
          {window.desktop.platform === "web" ? "Screen-based questions follow analysis of approved redacted frames. Typed notes and voice answers are handled separately from visual redaction." : "Use Ready for a question when you can pause, or answer later in Debrief."} The microphone opens only when you choose Voice.
        </p>
      </section>
    </aside>
  );
}
