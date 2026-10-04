import { LoaderCircle } from "lucide-react";
import { useApp } from "../stores";
import { usePrivacyJobs } from "../privacy/service";

const labels: Record<string, string> = {
  observer: "Understanding screen actions…", assessment: "Evaluating context and process scores…",
  knowledge: "Building process steps and your Work Map…", interviewer: "Preparing a reviewer question…",
  practice: "Preparing practice exercises…", tutor: "Evaluating your answer…", coach: "Reviewing your progress…",
};
export function ProcessingStatus() {
  const data = useApp((s) => s.data), job = usePrivacyJobs();
  const stage = (data?.processing || data?.busy || [])[0];
  const local = job.session === data?.session?.id && job.label;
  if (!local && !stage) return null;
  return <div className="notice-banner processing-status" role="status" aria-live="polite">
    <LoaderCircle className="processing-spinner" size={19} />
    <span><strong>Context processing</strong><br />{local || labels[stage!] || "Preparing results…"}</span>
    {local && <progress aria-label={job.label} max={1} value={job.label.startsWith("Evaluating context") || job.label.startsWith("Building process") ? undefined : job.progress} />}
  </div>;
}

export function ApprovedAnalysisNotice() {
  const data = useApp((s) => s.data);
  const privacy = data?.session?.privacy;
  if (window.desktop.platform !== "web" || data?.question || !privacy || privacy.status !== "approved" ||
      privacy.question_revision !== privacy.revision || !privacy.analyzed_frames?.length) return null;
  const noQuestion = data.session!.messages.some((m) => m.text.startsWith("Analysis complete. No supported screen question"));
  return <div className="notice-banner" role="status">
    <span>{noQuestion ? "Analysis complete. The current evidence does not support a new screen question. Add context or review the findings in Debrief." : "Approved-frame analysis is complete. Your questions and explanations are saved in Debrief."}</span>
    <button className="text-button" onClick={() => useApp.getState().go("Debrief")}>Open Debrief</button>
  </div>;
}
