/** Shared wire contract. No media, OCR values, credentials or unrestricted commands. */
export type Snapshot = {
  connected: boolean;
  epoch: string;
  sequence: number;
  session: string | null;
  question: { id: string; text: string } | null;
  recording: string;
  voice: string;
  muted: boolean;
  privacy: string;
  busy: boolean;
};
export const offline: Snapshot = {
  connected: false,
  epoch: "",
  sequence: 0,
  session: null,
  question: null,
  recording: "idle",
  voice: "idle",
  muted: true,
  privacy: "pending",
  busy: false,
};
export type Action = {
  type: "command";
  id: string;
  epoch: string;
  session: string | null;
  question: string | null;
  action: "record" | "context" | "voice" | "mute" | "open" | "defer";
  text?: string;
};
const short = (v: unknown, max = 200): v is string =>
  typeof v === "string" && v.length <= max;
export function validAction(v: any): v is Action {
  return (
    !!v &&
    v.type === "command" &&
    short(v.id, 64) &&
    /^[a-z0-9-]{16,64}$/i.test(v.id) &&
    short(v.epoch) &&
    (v.session === null || short(v.session)) &&
    (v.question === null || short(v.question)) &&
    ["record", "context", "voice", "mute", "open", "defer"].includes(
      v.action,
    ) &&
    (v.text === undefined || short(v.text, 12000))
  );
}
export function validSnapshot(v: any): v is Snapshot {
  return (
    !!v &&
    typeof v.connected === "boolean" &&
    short(v.epoch) &&
    Number.isSafeInteger(v.sequence) &&
    v.sequence >= 0 &&
    (v.session === null || short(v.session)) &&
    (v.question === null ||
      (short(v.question?.id) && short(v.question?.text, 12000))) &&
    ["idle", "paused", "recording"].includes(v.recording) &&
    ["idle", "listening", "thinking", "speaking"].includes(v.voice) &&
    typeof v.muted === "boolean" &&
    short(v.privacy) &&
    typeof v.busy === "boolean"
  );
}
export function validOrigin(value: string) {
  try {
    const u = new URL(value);
    return (
      u.origin === value &&
      (u.protocol === "https:" ||
        (u.protocol === "http:" &&
          ["localhost", "127.0.0.1"].includes(u.hostname)))
    );
  } catch {
    return false;
  }
}
