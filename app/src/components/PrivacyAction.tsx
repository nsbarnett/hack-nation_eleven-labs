import { useApp, run } from "../stores";
import type { State } from "../types";

export function PrivacyAction({ workflow }: { workflow: State["sessions"][number] }) {
  if (window.desktop.platform !== "web" || !workflow.privacy_action) return null;
  const review = workflow.privacy_action === "review";
  return <div className="workflow-privacy-action">
    <span className="action-required">Action needed</span>
    <p>{review ? "Review and approve this recording before AI can create screen-based steps and questions." : "Recording approved. Analyze approved frames to create steps and questions."}</p>
    <button className="button" onClick={() => run(async () => {
      if (useApp.getState().data?.session?.id !== workflow.id) await useApp.getState().command("open", { id: workflow.id });
      useApp.getState().go("Privacy Review");
    })}>{review ? "Review privacy" : "Continue to analysis"}</button>
  </div>;
}
