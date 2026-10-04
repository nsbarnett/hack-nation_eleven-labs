import { useState } from "react";
import { GraduationCap, Monitor, ArrowUp } from "lucide-react";
import { useApp, useMedia, run } from "../stores";
import { stopRecording } from "../media";
import { Button, Empty } from "../components/Controls";
import { CloudConsent } from "../components/CloudConsent";
export function Teach({ onRecord }: { onRecord: () => void }) {
  const data = useApp((s) => s.data)!;
  const recording = useMedia((s) => s.status.state);
  const [mode, setMode] = useState<"practice" | "live">("practice");
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [text, setText] = useState("");
  if (!data.session?.confirmed)
    return (
      <Empty
        icon={<GraduationCap size={30} />}
        heading="Teaching starts with confirmed knowledge"
      >
        Open a workflow, review each step, and confirm its Work Map before
        creating exercises or starting live coaching.
      </Empty>
    );
  return (
    <>
      <header className="page-heading compact">
        <span className="eyebrow">LEARN THE JUDGMENT, NOT JUST THE STEPS</span>
        <h1>Teach Mode</h1>
        <p>Grounded in the confirmed Work Map for {data.session.title}.</p>
      </header>
      <CloudConsent />
      <div className="segmented">
        <button
          aria-pressed={mode === "practice"}
          onClick={() => setMode("practice")}
        >
          Guided practice
        </button>
        <button aria-pressed={mode === "live"} onClick={() => setMode("live")}>
          Live coaching
        </button>
      </div>
      {mode === "practice" ? (
        <>
          <div className="section-heading">
            <p className="muted">
              Generated hypothetical exercises ·{" "}
              {Object.keys(data.practice.answers).length} of{" "}
              {data.practice.items.length} answered
            </p>
            <Button
              className="primary"
              disabled={!!data.busy.length}
              onClick={() => run(() => useApp.getState().command("practice"))}
            >
              {data.busy.includes("practice")
                ? "Creating…"
                : "Generate practice"}
            </Button>
          </div>
          {data.practice.items.map((item, index) => (
            <section
              className="panel exercise"
              key={`${index}-${item.question}`}
            >
              <span className="eyebrow">GENERATED PRACTICE · {index + 1}</span>
              <h3>{item.question}</h3>
              <p className="small muted">
                Based on {item.knowledge_ids.length} confirmed step
                {item.knowledge_ids.length === 1 ? "" : "s"}.
              </p>
              <textarea
                aria-label={`Answer exercise ${index + 1}`}
                placeholder="Explain what you would do and why…"
                value={answers[index] || ""}
                onChange={(e) =>
                  setAnswers({ ...answers, [index]: e.target.value })
                }
              />
              <Button
                disabled={!answers[index]?.trim() || !!data.busy.length}
                onClick={() =>
                  run(() =>
                    useApp
                      .getState()
                      .command("tutor", { index, text: answers[index] }),
                  )
                }
              >
                Get feedback
              </Button>
              {data.practice.answers[String(index)] && (
                <div className="feedback">
                  <span className="badge">
                    AI advisory feedback ·{" "}
                    {data.practice.answers[String(index)].verdict}
                  </span>
                  <p>{data.practice.answers[String(index)].explanation}</p>
                </div>
              )}
            </section>
          ))}
          {!data.practice.items.length && (
            <Empty
              icon={<GraduationCap size={28} />}
              heading="Practice the decisions that matter"
            >
              Generate questions from this confirmed map. Insufficient knowledge
              produces no exercises rather than invented rules.
            </Empty>
          )}
        </>
      ) : (
        <section className="panel exercise">
          <Monitor size={28} />
          <h2>An apprentice beside you.</h2>
          <p>
            The tutor compares sampled screens with confirmed knowledge and
            offers advisory guidance. It cannot prevent or perform actions in
            other applications.
          </p>
          <Button
            className={data.coaching ? "" : "primary"}
            onClick={() =>
              run(async () => {
                if (data.coaching) {
                  await stopRecording();
                  await useApp
                    .getState()
                    .command("coaching", { enabled: false });
                } else {
                  await useApp.getState().command("cloud", { enabled: true });
                  await useApp
                    .getState()
                    .command("coaching", { enabled: true });
                  onRecord();
                }
              })
            }
          >
            {data.coaching ? "End coaching" : "Choose screen for live coaching"}
          </Button>
          <p className="small muted">
            {data.coaching
              ? recording === "recording"
                ? "Observing trainee work."
                : "Coaching is prepared; choose a screen to begin capture."
              : "Trainee behavior is stored separately and never becomes an expert rule."}
          </p>
        </section>
      )}
      <section className="panel tutor-chat">
        <h3>Ask about this workflow</h3>
        <div className="messages">
          {data.session.messages.slice(-6).map((m) => (
            <div key={m.id} className={`message ${m.role}`}>
              <span>{m.role === "assistant" ? "Apprentice" : "You"}</span>
              <p>{m.text}</p>
            </div>
          ))}
        </div>
        <form
          className="composer"
          onSubmit={(e) => {
            e.preventDefault();
            run(async () => {
              await useApp.getState().command("tutor", { text });
              setText("");
            });
          }}
        >
          <input
            aria-label="Ask the tutor"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Ask about a decision or guardrail…"
          />
          <button
            className="send"
            disabled={!text.trim() || !!data.busy.length}
            aria-label="Ask tutor"
          >
            <ArrowUp size={17} />
          </button>
        </form>
      </section>
    </>
  );
}
