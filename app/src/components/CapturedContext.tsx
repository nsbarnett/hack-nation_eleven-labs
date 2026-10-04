import { useApp } from "../stores";

export function CapturedContext() {
  const session = useApp((s) => s.data?.session);
  if (!session) return null;
  const notes = session.evidence.filter((e) => e.text && !e.kind.startsWith("trainee"));
  return <section className="panel evaluation-panel" aria-label="Captured context">
    <h2>Captured context</h2>
    {session.context && <p>{session.context}</p>}
    <p>{session.observations.length} observed steps · {notes.length} notes and explanations · {session.knowledge.length} Work Map steps</p>
    {!!session.observations.length && <ol>{session.observations.map((o) => <li key={o.id}>{o.summary}</li>)}</ol>}
    {!!notes.length && <details><summary>Read saved notes and explanations</summary>{notes.map((e) => <p key={e.id}>{e.text}</p>)}</details>}
    {!session.observations.length && !!session.recordings.length && <p>{session.privacy.status !== "approved" ? "Screen content is waiting for Privacy Review. Your notes remain available here." : session.privacy.question_revision !== session.privacy.revision ? "Approved frames still need analysis in Privacy Review." : "No meaningful visible changes were identified in the selected frames. Add a note explaining the action or capture clearer before-and-after views."}</p>}
    {!!session.recordings.length && session.privacy.question_revision !== session.privacy.revision && <button className="button" onClick={() => useApp.getState().go("Privacy Review")}>Continue in Privacy Review</button>}
  </section>;
}
