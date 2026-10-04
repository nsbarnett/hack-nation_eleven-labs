import { AudioLines } from "lucide-react";
export function VoiceOrb({
  active = false,
  muted = false,
  recording = false,
}: {
  active?: boolean;
  muted?: boolean;
  recording?: boolean;
}) {
  return (
    <span
      className={`voice-orb ${active ? "active" : ""} ${muted ? "muted" : ""}`}
    >
      <AudioLines size={29} strokeWidth={1.6} />
      {recording && <span className="record-dot" />}
    </span>
  );
}
