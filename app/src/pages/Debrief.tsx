import { MessageCircle, ArrowRight } from "lucide-react";
import { useApp, run } from "../stores";
import { Button, Empty } from "../components/Controls";
import { AssistantPanel } from "../components/AssistantPanel";
import { EvaluationPanel } from "../components/EvaluationPanel";
export function Debrief() {
  const data = useApp((s) => s.data)!;
  if (!data.session)
    return (
      <Empty heading="Choose a workflow to debrief">
        Open your recorded work first.
      </Empty>
    );
  return (
    <>
      <header className="page-heading compact">
        <span className="eyebrow">MAKE THE IMPLICIT EXPLICIT</span>
        <h1>What should someone else know?</h1>
        <p>
          Close the gaps behind {data.session.title}. The apprentice asks one
          supported question at a time.
        </p>
      </header>
      <div className="debrief-layout">
        <section className="panel debrief-card">
          <MessageCircle size={30} />
          <h2>Capture the why.</h2>
          <p>
            Explain the exceptions, decisions, and guardrails that a recording
            alone cannot show.
          </p>
          {data.question ? (
            <blockquote>{data.question.text}</blockquote>
          ) : (
            <p className="muted">
              Request a question when you are ready. No questions are invented
              when the evidence does not support one.
            </p>
          )}
          <div className="button-row">
            <Button
              className="primary"
              disabled={!!data.busy.length || !data.session.evidence.length}
              onClick={() => run(() => useApp.getState().command("debrief"))}
            >
              {data.busy.includes("interviewer")
                ? "Thinking…"
                : "Ask the next question"}
              <ArrowRight size={15} />
            </Button>
            <Button onClick={() => useApp.getState().go("Work Map")}>
              Review Work Map
            </Button>
          </div>
        </section>
        <AssistantPanel />
      </div>
      <EvaluationPanel />
    </>
  );
}
