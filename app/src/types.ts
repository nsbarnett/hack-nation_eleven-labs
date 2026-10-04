/** Renderer contracts: secrets and backend addresses are intentionally absent. */
export type Evidence = {
  id: string;
  kind: string;
  text: string;
  image: string;
  timestamp: number;
  question: string;
  related_ids: string[];
};
export type Knowledge = {
  id: string;
  title: string;
  action: string;
  decision: string;
  reason: string;
  rule: string;
  exception: string;
  guardrail: string;
  escalation: string;
  evidence_ids: string[];
  status: string;
};
export type Workflow = {
  id: string;
  title: string;
  context: string;
  duration: number;
  confirmed: boolean;
  phase: string;
  evidence: Evidence[];
  knowledge: Knowledge[];
  recordings: string[];
  observations: { id: string; summary: string; evidence_ids: string[] }[];
  messages: { id: string; role: string; text: string }[];
};
export type MediaStatus = {
  state: "idle" | "recording" | "paused";
  muted: boolean;
  voice: string;
  duration: number;
};
export type State = {
  epoch?: string;
  hosted?: boolean;
  guest?: string;
  limits?: { recordingSeconds: number; mediaBytes: number; dailyAiCalls: number };
  sequence: number;
  session: Workflow | null;
  sessions: {
    id: string;
    title: string;
    updated: string;
    confirmed: boolean;
    steps: number;
    duration: number;
  }[];
  cloud: boolean;
  recording: string;
  assistant: string;
  question: { id: string; text: string; evidence_ids: string[] } | null;
  busy: string[];
  coaching: boolean;
  practice: {
    items: { question: string; knowledge_ids: string[] }[];
    answers: Record<string, { verdict: string; explanation: string }>;
  };
  credentials: {
    openai: boolean;
    elevenlabs: boolean;
    voiceId: string;
    model: string;
  };
  media: MediaStatus;
  version: string;
};
export type Source = {
  id: string;
  name: string;
  thumbnail: string;
  displayId: string;
};
export type Desktop = {
  platform: string;
  state(): Promise<State>;
  command(name: string, data?: unknown): Promise<any>;
  sources(): Promise<Source[]>;
  selectSource(id: string): Promise<void>;
  beginSegment(): Promise<string>;
  chunk(id: string, bytes: Uint8Array): Promise<void>;
  endSegment(id: string): Promise<void>;
  frame(bytes: Uint8Array, duration: number): Promise<void>;
  speech(text: string): Promise<Uint8Array>;
  transcribe(bytes: Uint8Array): Promise<{ text: string }>;
  saveCredentials(values: Record<string, string>): Promise<void>;
  checkCredentials(provider: string): Promise<{ ok: boolean }>;
  importLegacy(): Promise<{ count: number }>;
  exportMap(): Promise<{ path?: string }>;
  media(relative: string): Promise<string | null>;
  window(action: string): Promise<void>;
  overlay(expanded: boolean, question: boolean): Promise<void>;
  drag(dx: number, dy: number): Promise<void>;
  passthrough(enabled: boolean): Promise<void>;
  relay(action: string): Promise<void>;
  status(status: MediaStatus): Promise<void>;
  onEvent(callback: (event: any) => void): () => void;
  quit(): Promise<void>;
};
declare global {
  interface Window {
    desktop: Desktop;
  }
}
