import { useState } from "react";
import { GitBranch, Search, ArrowUpRight } from "lucide-react";
import { useApp, run } from "../stores";
import { Empty, Button } from "../components/Controls";
import { DeleteWorkflow } from "../components/DeleteWorkflow";
import { PrivacyAction } from "../components/PrivacyAction";
export function Workflows({ onRecord }: { onRecord: () => void }) {
  const [query, setQuery] = useState("");
  const sessions = useApp((s) => s.data!.sessions);
  return (
    <>
      <header className="page-heading compact">
        <span className="eyebrow">KNOWLEDGE YOU CAN RETURN TO</span>
        <h1>Workflows</h1>
        <p>Your recorded processes and the reasoning behind them.</p>
      </header>
      <div className="section-heading">
        <label className="search">
          <Search size={17} />
          <input
            aria-label="Search workflows"
            placeholder="Search your workflows"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <Button className="primary" onClick={onRecord}>
          Record a workflow
        </Button>
      </div>
      <div className="workflow-grid">
        {sessions
          .filter((s) => s.title.toLowerCase().includes(query.toLowerCase()))
          .map((s) => (
            <article key={s.id} className="workflow-card panel">
            <button
              key={s.id}
              className="workflow-open"
              onClick={() =>
                run(async () => {
                  await useApp.getState().command("open", { id: s.id });
                  useApp.getState().go("Work Map");
                })
              }
            >
              <div className="section-heading">
                <GitBranch size={22} />
                <ArrowUpRight size={18} />
              </div>
              <h3>{s.title}</h3>
              <p>
                {s.steps} steps · {new Date(s.updated).toLocaleDateString()}
              </p>
              <span className={`badge ${s.confirmed ? "verified" : ""}`}>
                {s.confirmed ? "Expert confirmed" : "Draft"}
              </span>
            </button>
            <PrivacyAction workflow={s} />
            <DeleteWorkflow workflow={s} />
            </article>
          ))}
      </div>
      {!sessions.length && (
        <Empty icon={<GitBranch size={28} />} heading="No workflows yet">
          Start with a real task. The apprentice will help turn your decisions
          into a Work Map.
        </Empty>
      )}
      {!!sessions.length &&
        !sessions.some((s) =>
          s.title.toLowerCase().includes(query.toLowerCase()),
        ) && <Empty heading="No matching workflows">Try another search.</Empty>}
    </>
  );
}
