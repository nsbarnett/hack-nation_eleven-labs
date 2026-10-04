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
  decision_ids?: string[];
  check_verified?: boolean;
  check?: { conditions: { field: string; operator: string; value: string }[]; field: string; operator: string; value: string } | null;
};
export type Evaluation = {
  debrief_complete: boolean;
  open_critical: string[];
  dimensions: {
    observation_quality: { usable: number; total: number };
    answer_sufficiency: { pending_evidence: number; partial: number };
    rule_completeness: { unresolved: number; total: number };
    consistency: { disputed: number };
    verification: { verified: number; total: number };
    learner_correctness: { method: string };
  };
  gaps: { id: string; decision_id: string; field: string; description: string; status: string; claim: string; evidence_ids: string[] }[];
  trace: { code: string; gap_id: string; detail: string }[];
};
export type Workflow = {
  privacy: { revision: number; status: "unreviewed" | "approved"; analyzed_frames?: string[] };
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
  evaluation?: Evaluation | null;
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
    items: { question: string; knowledge_ids: string[]; scenario?: { field: string; value: string }[]; answer_fields?: string[] }[];
    answers: Record<string, { verdict: string; explanation: string; evaluation_method?: string }>;
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
  beginSegment(metadata?: { start: number; width: number; height: number }): Promise<string>;
  chunk(id: string, bytes: Uint8Array): Promise<void>;
  endSegment(id: string, duration?: number, partial?: boolean): Promise<void>;
  reviewedFrame?(bytes: Uint8Array, duration: number, id: string, sessionId: string, revision: number): Promise<void>;
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
