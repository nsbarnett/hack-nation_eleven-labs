import { useState } from "react";
import { useApp, run } from "../stores";
import { Button } from "./Controls";

export function EvaluationPanel() {
  const data = useApp((s) => s.data)!;
  const [reviewing, setReviewing] = useState("");
  const [text, setText] = useState("");
  const [outcome, setOutcome] = useState("verified");
  const report = data.evaluation;
  if (!report) return null;
  const d = report.dimensions;
  const rows = [
    ["Observation quality", `${d.observation_quality.usable} of ${d.observation_quality.total} visible decisions supported`],
    ["Answer sufficiency", `${d.answer_sufficiency.pending_evidence} explanations awaiting assessment; ${d.answer_sufficiency.partial} partial`],
    ["Rule completeness", `${d.rule_completeness.unresolved} unresolved gaps`],
    ["Consistency", `${d.consistency.disputed} disputed fields`],
    ["Expert verification", `${d.verification.verified} of ${d.verification.total} fields reviewed`],
    ["Learner evaluation", "Reviewed rule checks for structured cases; advisory feedback for written explanations"],
  ];
  return (
    <section className="panel evaluation-panel" aria-label="Knowledge evaluation">
      <h2>What is established?</h2>
      <p><strong>Process evidence completeness: {report.process_score == null ? "Awaiting evidence" : `${report.process_score}%`}</strong>. This measures captured explanations, not expert verification or a person's performance.</p>
      <p className="muted">{report.debrief_complete ? "No known applicable gaps remain. Expert map review is still required before teaching." : "Open gaps remain visible until supported evidence or explicit expert review resolves them."}</p>
      <dl className="evaluation-dimensions">{rows.map(([name, value]) => <div key={name}><dt>{name}</dt><dd>{value}</dd></div>)}</dl>
      {d.answer_sufficiency.pending_evidence > 0 && <p className="small">Request the next debrief question or rebuild the map to assess newly saved explanations.</p>}
      <details>
        <summary>Review knowledge gaps ({report.gaps.length})</summary>
        {report.gaps.map((gap) => (
          <article className="evaluation-gap" key={gap.id}>
            <div className="section-heading"><strong>{gap.field}</strong><span className="badge">{gap.status.replaceAll("_", " ")}</span></div>
            <p>{gap.description}</p>
            {gap.claim && <p className="small">Current statement: {gap.claim}</p>}
            <p className="small muted">Sources: {gap.evidence_ids.map((id) => id.slice(0, 8)).join(", ")}</p>
            <Button disabled={!!data.busy.length || data.recording !== "idle"} onClick={() => { setReviewing(gap.id); setText(""); setOutcome("verified"); }}>Review clarification</Button>
            {reviewing === gap.id && <form className="evaluation-review" onSubmit={(event) => {
              event.preventDefault();
              run(async () => {
                await useApp.getState().command("review-gap", { id: gap.id, text, outcome });
                setReviewing(""); setText("");
              });
            }}>
              <label className="field">Expert clarification<textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="State the applicable rule and conditions, resolve the conflict, or explain why this field does not apply." /></label>
              <label className="field">Review decision<select value={outcome} onChange={(e) => setOutcome(e.target.value)}><option value="verified">I confirm this clarification</option><option value="not_applicable">This field does not apply</option></select></label>
              <p className="small muted">Your statement is saved as expert evidence. Confirm only what you can establish for this decision.</p>
              <div className="button-row"><Button className="primary" disabled={!text.trim() || !!data.busy.length}>Save expert review</Button><Button type="button" onClick={() => setReviewing("")}>Cancel</Button></div>
            </form>}
          </article>
        ))}
      </details>
      <details><summary>Why questions were selected or gaps changed</summary><ol className="evaluation-trace">{report.trace.map((entry, index) => <li key={`${index}-${entry.code}`}>{entry.detail}</li>)}</ol></details>
    </section>
  );
}
