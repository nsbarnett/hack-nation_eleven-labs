import { useEffect, useRef } from "react";
import { Monitor, Pause, Play, Square, Video, Clock } from "lucide-react";
import { useApp, useMedia, run } from "../stores";
import { stopRecording, startRecording, canResume } from "../media";
import { Button, Empty } from "../components/Controls";
import { AssistantPanel } from "../components/AssistantPanel";
export function duration(value: number) {
  return new Date(value * 1000).toISOString().slice(11, 19);
}
export function Record({ onRecord }: { onRecord: () => void }) {
  const session = useApp((s) => s.data?.session);
  const media = useMedia();
  const ref = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.srcObject = media.stream;
  }, [media.stream, media.safePreview]);
  return (
    <>
      <div className="record-bar panel">
        <span
          className={`record-indicator ${media.status.state === "recording" ? "on" : ""}`}
        >
          <span />
        </span>
        <strong>
          {media.status.state === "recording"
            ? "Recording"
            : media.status.state === "paused"
              ? "Paused"
              : "Ready to record"}
        </strong>
        <span className="timer">
          {duration(
            media.status.state === "idle"
              ? session?.duration || 0
              : media.status.duration,
          )}
        </span>
        <div className="spacer" />
        {media.status.state === "recording" ? (
          <>
            <Button onClick={() => run(() => stopRecording(true))}>
              <Pause size={15} />
              Pause
            </Button>
            <Button
              className="danger"
              onClick={() => run(() => stopRecording())}
            >
              <Square size={14} />
              Stop
            </Button>
          </>
        ) : media.status.state === "paused" ? (
          <>
            <Button
              className="primary"
              onClick={() =>
                canResume() ? run(() => startRecording()) : onRecord()
              }
            >
              <Play size={15} />
              Resume
            </Button>
            <Button onClick={() => run(() => stopRecording())}>Finish</Button>
          </>
        ) : (
          <Button className="primary" onClick={onRecord}>
            <Video size={16} />
            Record
          </Button>
        )}
      </div>
      <div className="record-layout">
        <div className="record-workspace">
          <section className="preview panel">
            {media.stream && media.safePreview ? (
              <video ref={ref} autoPlay muted playsInline />
            ) : (
              <Empty
                icon={<Monitor size={35} />}
                heading={
                  media.stream
                    ? "Recording your display"
                    : session?.title || "Choose a task to capture"
                }
              >
                {media.stream
                  ? "Preview is hidden while capturing an entire display to avoid recording a repeating mirror of this window. Your recording continues."
                  : "Choose a window or display to begin. Your screen preview will appear here when it can be shown safely."}
              </Empty>
            )}
            <div className="preview-caption">
              <Monitor size={14} />
              {media.sourceName || "No capture source selected"}
            </div>
          </section>
          <section className="panel timeline">
            <div className="section-heading">
              <h3>Process timeline</h3>
              <span className="small muted">
                {session?.observations.length || 0} observed steps
              </span>
            </div>
            {session?.observations.length ? (
              session.observations.map((item, index) => (
                <div className="timeline-row" key={item.id}>
                  <span className="step-number">{index + 1}</span>
                  <div>
                    <strong>{item.summary}</strong>
                    <p>{item.evidence_ids.length} linked sources</p>
                  </div>
                </div>
              ))
            ) : (
              <Empty
                icon={<Clock size={22} />}
                heading="A clear trail of your work"
              >
                With cloud analysis enabled, meaningful observed actions appear
                here. You can add notes at any time while recording.
              </Empty>
            )}
          </section>
        </div>
        <AssistantPanel />
      </div>
    </>
  );
}
