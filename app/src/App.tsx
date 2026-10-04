import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  Home as HomeIcon,
  Video,
  GitBranch,
  Map,
  MessageCircle,
  GraduationCap,
  Library as LibraryIcon,
  Settings as SettingsIcon,
  AudioLines,
  ArrowUpRight,
  X,
  ShieldCheck,
} from "lucide-react";
import { useApp, useMedia, run } from "./stores";
import type { Page } from "./stores";
import { stopRecording, voiceNote, toggleMute } from "./media";
import { Home } from "./pages/Home";
import { Record } from "./pages/Record";
import { Workflows } from "./pages/Workflows";
import { WorkMap } from "./pages/WorkMap";
import { Debrief } from "./pages/Debrief";
import { Teach } from "./pages/Teach";
import { Library } from "./pages/Library";
import { PrivacyReview } from "./pages/PrivacyReview";
import { Settings } from "./pages/Settings";
import { RecordingSetup } from "./components/RecordingSetup";
import { ProcessingStatus, ApprovedAnalysisNotice } from "./components/ProcessingStatus";
import { ReviewerQuestion } from "./components/ReviewerQuestion";
import { WorkflowDeletionDialog } from "./components/DeleteWorkflow";
import { contentTransition } from "./animations";
import { downloadDiagnostics } from "./web/diagnostics";
const navigation: { name: Page; icon: typeof HomeIcon }[] = [
  { name: "Home", icon: HomeIcon },
  { name: "Record", icon: Video },
  { name: "Workflows", icon: GitBranch },
  { name: "Work Map", icon: Map },
  { name: "Debrief", icon: MessageCircle },
  { name: "Teach", icon: GraduationCap },
  { name: "Library", icon: LibraryIcon },
];
export function App() {
  const page = useApp((s) => s.page),
    go = useApp((s) => s.go),
    data = useApp((s) => s.data),
    error = useApp((s) => s.error);
  const [setup, setSetup] = useState(false),
    [newWorkflow, setNewWorkflow] = useState(true);
  const recording = useMedia((s) => s.status.state);
  const notice = useApp((s) => s.notice);
  function record(fresh = true) {
    void window.desktop.window("open");
    setNewWorkflow(fresh);
    setSetup(true);
  }
  useEffect(
    () =>
      window.desktop.onEvent((event) => {
        if (event.type === "action") {
          if (event.action === "record") {
            if (useMedia.getState().status.state !== "idle")
              run(() => stopRecording());
            else record(!useApp.getState().data?.session);
          }
          if (event.action === "voice") run(voiceNote);
          if (event.action === "mute") toggleMute();
          if (event.action === "context") {
            useApp.setState({ focusContext: true });
            go("Record");
          }
        }
        if (event.type === "closing")
          run(async () => {
            await stopRecording();
            await window.desktop.quit();
          });
        if (event.type === "backend-offline") run(() => stopRecording());
      }),
    [go],
  );
  if (!data)
    return (
      <div className="startup">
        <AudioLines size={36} />
        <h2>Opening Apprentice…</h2>
        {error && <><p role="alert">{error}</p><button className="button" onClick={() => { useApp.setState({ error: "" }); void useApp.getState().refresh(); }}>Try again</button></>}
      </div>
    );
  const pages: Record<Page, React.ReactNode> = {
    Home: <Home onRecord={() => record()} />,
    Record: <Record onRecord={() => record(!data.session)} />,
    Workflows: <Workflows onRecord={() => record()} />,
    "Work Map": <WorkMap />,
    Debrief: <Debrief />,
    Teach: <Teach onRecord={() => record(false)} />,
    Library: <Library />,
    "Privacy Review": <PrivacyReview />,
    Settings: <Settings />,
  };
  return (
    <div className={`app-shell ${window.desktop.platform === "web" ? "web-shell" : ""}`}>
      {window.desktop.platform !== "web" && <div
        className={`titlebar ${window.desktop.platform === "darwin" ? "mac" : ""}`}
      >
        <span>AI Apprentice</span>
        <span className="titlebar-subtitle">Capture. Understand. Teach.</span>
      </div>}
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            go("Home");
          }}
        >
          <span>
            <AudioLines size={19} />
          </span>
          Apprentice
        </a>
        <nav aria-label="Main navigation">
          {[...navigation, ...(window.desktop.platform === "web" ? [{ name: "Privacy Review" as Page, icon: ShieldCheck }] : [])].map(({ name, icon: Icon }) => (
            <button
              key={name}
              aria-label={name}
              aria-describedby={name === "Privacy Review" && data.sessions.some((s) => s.privacy_action) ? "privacy-nav-action" : undefined}
              className={page === name ? "selected" : ""}
              onClick={() => run(async () => {
                if (name === "Privacy Review" && recording === "idle" && !data.sessions.some((s) => s.id === data.session?.id && s.privacy_action)) {
                  const pending = data.sessions.find((s) => s.privacy_action);
                  if (pending && pending.id !== data.session?.id) await useApp.getState().command("open", { id: pending.id });
                }
                go(name);
              })}
            >
              <Icon size={17} />
              {name}
              {name === "Privacy Review" && data.sessions.some((s) => s.privacy_action) && (
                <span id="privacy-nav-action" className="nav-action-required" title="Review and analyze this recording to receive screen-based steps and questions">Action needed</span>
              )}
              {name === "Record" && recording === "recording" && (
                <span className="nav-record-dot" />
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <span>
              Knowledge grows
              <br />
              when experience
              <br />
              is shared.
            </span>
            <div className="quiet-wave" />
          </div>
          <button
            className={page === "Settings" ? "selected" : ""}
            onClick={() => go("Settings")}
          >
            <SettingsIcon size={17} />
            Settings
          </button>
          <small>AI Apprentice · {data.version}</small>
        </div>
      </aside>
      <main className="main-content">
        <ProcessingStatus />
        <ApprovedAnalysisNotice />
        {notice && <div className="notice-banner" role="status"><span>{notice}</span><button aria-label="Dismiss notice" onClick={() => useApp.setState({ notice: "" })}><X size={16} /></button></div>}
        {error && (
          <div className="error-banner" role="alert">
            <span>{error}</span>
            {window.desktop.platform === "web" && <button className="text-button" onClick={downloadDiagnostics}>Download diagnostic log</button>}
            <button
              aria-label="Dismiss error"
              onClick={() => useApp.setState({ error: "" })}
            >
              <X size={16} />
            </button>
          </div>
        )}
        <div className="workspace-top">
          <span>{page === "Home" ? "Workspace" : page}</span>
          {data.session && (
            <button onClick={() => go("Work Map")}>
              {data.session.title}
              <ArrowUpRight size={14} />
            </button>
          )}
        </div>
        <AnimatePresence mode="wait">
          <motion.div key={page} {...contentTransition}>
            {pages[page]}
          </motion.div>
        </AnimatePresence>
      </main>
      <RecordingSetup
        open={setup}
        onChange={setSetup}
        newWorkflow={newWorkflow}
      />
      {window.desktop.platform === "web" && <ReviewerQuestion />}
      {window.desktop.platform === "web" && <WorkflowDeletionDialog />}
    </div>
  );
}
