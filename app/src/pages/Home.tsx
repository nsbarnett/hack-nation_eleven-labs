import {
  Video,
  GitBranch,
  GraduationCap,
  ArrowUpRight,
  ArrowRight,
} from "lucide-react";
import { useApp, run } from "../stores";
import { Button, Empty } from "../components/Controls";
export function Home({ onRecord }: { onRecord: () => void }) {
  const sessions = useApp((s) => s.data!.sessions);
  const go = useApp((s) => s.go);
  return (
    <>
      <header className="page-heading">
        <span className="eyebrow">YOUR WORK, UNDERSTOOD</span>
        <h1>
          Make experience
          <br />
          something you can share.
        </h1>
        <p>Capture the task. Understand the decisions. Teach what matters.</p>
      </header>
      <div className="action-grid">
        <Action
          icon={<Video />}
          title="Record a workflow"
          text="Let the apprentice learn how and why you work."
          action="Start recording"
          onClick={onRecord}
        />
        <Action
          icon={<GitBranch />}
          title="Explore your Work Maps"
          text="Review the decisions, evidence, and guardrails you have captured."
          action="View workflows"
          onClick={() => go("Workflows")}
        />
        <Action
          icon={<GraduationCap />}
          title="Teach someone"
          text="Turn confirmed knowledge into practice and live guidance."
          action="Open Teach Mode"
          onClick={() => go("Teach")}
        />
      </div>
      <div className="section-heading">
        <h2>Recent workflows</h2>
        <button className="text-button" onClick={() => go("Workflows")}>
          View all <ArrowUpRight size={15} />
        </button>
      </div>
      {sessions.length ? (
        <div className="panel workflow-list">
          {sessions.slice(0, 5).map((s) => (
            <button
              className="workflow-row"
              key={s.id}
              onClick={() =>
                run(async () => {
                  await useApp.getState().command("open", { id: s.id });
                  go("Work Map");
                })
              }
            >
              <span className="workflow-icon">
                <GitBranch size={18} />
              </span>
              <span>
                <strong>{s.title}</strong>
                <small>
                  {new Date(s.updated).toLocaleDateString()} · {s.steps} steps
                </small>
              </span>
              <span className={`badge ${s.confirmed ? "verified" : ""}`}>
                {s.confirmed ? "Confirmed" : "Draft"}
              </span>
              <ArrowRight size={16} />
            </button>
          ))}
        </div>
      ) : (
        <div className="panel">
          <Empty
            icon={<GitBranch size={25} />}
            heading="Your first workflow starts here"
          >
            {window.desktop.platform === "web" ? "Record a task to begin. Your notes and Work Maps will appear here; recordings stay in this browser." : "Record a task or import your existing recordings in Settings. Your saved work will appear here."}
          </Empty>
        </div>
      )}
    </>
  );
}
function Action({
  icon,
  title,
  text,
  action,
  onClick,
}: {
  icon: React.ReactNode;
  title: string;
  text: string;
  action: string;
  onClick: () => void;
}) {
  return (
    <section className="action-card">
      <span className="action-icon">{icon}</span>
      <h3>{title}</h3>
      <p>{text}</p>
      <Button onClick={onClick}>
        {action}
        <ArrowUpRight size={15} />
      </Button>
    </section>
  );
}
