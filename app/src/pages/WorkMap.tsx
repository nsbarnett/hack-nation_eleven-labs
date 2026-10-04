import { useState } from "react";
import { Check, Download, GitBranch, Pencil, Sparkles } from "lucide-react";
import { useApp, run } from "../stores";
import { Button, Empty, Modal } from "../components/Controls";
import type { Knowledge } from "../types";
import { CloudConsent } from "../components/CloudConsent";
import { EvaluationPanel } from "../components/EvaluationPanel";
const fields = [
  "action",
  "decision",
  "reason",
  "rule",
  "exception",
  "guardrail",
  "escalation",
] as const;
export function WorkMap() {
  const data = useApp((s) => s.data)!;
  const session = data.session;
  const [editing, setEditing] = useState<Knowledge | null>(null);
  const [image, setImage] = useState<string | null>(null);
  if (!session)
    return (
      <Empty icon={<GitBranch size={28} />} heading="Open a workflow first">
        Choose a saved workflow or record a new one to explore its Work Map.
      </Empty>
    );
  return (
    <>
      <header className="page-heading compact">
        <span className="eyebrow">
          WORK MAP / {session.confirmed ? "CONFIRMED" : "DRAFT"}
        </span>
        <h1>{session.title}</h1>
        <p>
          {session.context ||
            "Review the actions, reasoning, and evidence captured in this workflow."}
        </p>
      </header>
      <div className="button-row">
        <Button
          onClick={() => run(() => useApp.getState().command("build-map"))}
          disabled={!!data.busy.length || !session.evidence.length}
        >
          <Sparkles size={15} />
          {data.busy.includes("knowledge")
            ? "Building…"
            : "Build from evidence"}
        </Button>
        <Button onClick={() => useApp.getState().go("Debrief")}>Debrief</Button>
        <Button onClick={() => run(() => window.desktop.exportMap())}>
          <Download size={15} />
          Export
        </Button>
        <Button
          className="primary"
          disabled={session.confirmed || !session.knowledge.length}
          onClick={() => run(() => useApp.getState().command("confirm"))}
        >
          <Check size={15} />
          {session.confirmed ? "Confirmed" : "Confirm reviewed map"}
        </Button>
      </div>
      <CloudConsent />
      <EvaluationPanel />
      <div className="map-list">
        {session.knowledge.map((item, index) => (
          <section key={item.id} className="panel map-step">
            <div className="section-heading">
              <span className="step-number">{index + 1}</span>
              <h3>{item.title}</h3>
              <span
                className={`badge ${item.status === "verified" ? "verified" : ""}`}
              >
                {item.status.replaceAll("_", " ")}
              </span>
              <Button onClick={() => setEditing({ ...item })}>
                <Pencil size={14} />
                Review
              </Button>
            </div>
            <dl>
              {fields.map((field) => (
                <div key={field}>
                  <dt>{field}</dt>
                  <dd>{item[field] || "Not established"}</dd>
                </div>
              ))}
            </dl>
            {item.check && <p className="small muted">Executable rule: {item.check_verified ? "reviewed for structured practice" : "needs separate expert review"}.</p>}
            <div className="evidence-links">
              {item.evidence_ids.map((id) => {
                const source = session.evidence.find((e) => e.id === id);
                return (
                  <button
                    key={id}
                    onClick={() =>
                      source?.image
                        ? run(async () =>
                            setImage(await window.desktop.media(source.image)),
                          )
                        : useApp.getState().go("Library")
                    }
                  >
                    Source {id.slice(0, 8)} · {source?.kind || "unavailable"}
                  </button>
                );
              })}
            </div>
          </section>
        ))}
      </div>
      {!session.knowledge.length && (
        <div className="panel">
          <Empty
            icon={<GitBranch size={28} />}
            heading="The reasoning belongs here"
          >
            Add notes and screen evidence, then build a draft map. You review
            and verify every step before it can be used for teaching.
          </Empty>
        </div>
      )}
      <Modal
        open={!!editing}
        onChange={(open) => {
          if (!open) setEditing(null);
        }}
        title="Review this step"
        description="Correct the wording against the source evidence before verifying it."
      >
        {editing && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              run(async () => {
                const patch = Object.fromEntries(
                  ["title", ...fields, "status", "check_verified"].map((k) => [
                    k,
                    editing[k as keyof Knowledge],
                  ]),
                );
                await useApp
                  .getState()
                  .command("edit-knowledge", { id: editing.id, patch });
                setEditing(null);
              });
            }}
          >
            <label className="field">
              Title
              <input
                value={editing.title}
                onChange={(e) =>
                  setEditing({ ...editing, title: e.target.value })
                }
              />
            </label>
            {fields.map((field) => (
              <label className="field" key={field}>
                {field}
                <textarea
                  value={editing[field]}
                  onChange={(e) =>
                    setEditing({ ...editing, [field]: e.target.value })
                  }
                />
              </label>
            ))}
            {editing.check && <fieldset className="evaluation-check">
              <legend>Executable rule for structured practice</legend>
              <p>When {editing.check.conditions.length ? editing.check.conditions.map((condition) => `${condition.field} ${condition.operator} ${condition.value}`).join(" AND ") : "the scoped workflow applies"}, require {editing.check.field} {editing.check.operator} {editing.check.value}.</p>
              <label className="evaluation-checkbox"><input type="checkbox" checked={!!editing.check_verified} onChange={(e) => setEditing({ ...editing, check_verified: e.target.checked })} /> I reviewed these fields, conditions, and exact operators against the expert evidence.</label>
              <p className="small muted">Changing this step's text clears the executable check. Rebuild the map and review the new check before using it for structured practice.</p>
            </fieldset>}
            <label className="field">
              Review status
              <select
                value={editing.status}
                onChange={(e) =>
                  setEditing({ ...editing, status: e.target.value })
                }
              >
                {[
                  "inferred",
                  "verified",
                  "needs_clarification",
                  "conflicting",
                  "rejected",
                ].map((value) => (
                  <option key={value} value={value}>
                    {value.replaceAll("_", " ")}
                  </option>
                ))}
              </select>
            </label>
            <Button className="primary full">Save review</Button>
          </form>
        )}
      </Modal>
      <Modal
        open={!!image}
        onChange={() => setImage(null)}
        title="Source evidence"
        description="The recorded frame linked to this step."
      >
        {image && (
          <img
            className="evidence-image"
            src={image}
            alt="Recorded source evidence"
          />
        )}
      </Modal>
    </>
  );
}
