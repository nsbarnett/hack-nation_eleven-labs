/** Keep bounded operational metadata only: never bodies, query values, notes or media. */
export type Diagnostic = {
  time: string; event: string; operation: string; requestId?: string; method?: string;
  endpoint?: string; status?: number; elapsedMs?: number; category?: string;
  online?: boolean; jobId?: string; code?: number; clean?: boolean;
};
const entries: Diagnostic[] = [];
let serverVersion = "unknown", serverRevision = "unknown";
export function diagnostic(value: Omit<Diagnostic, "time">) {
  const entry = { time: new Date().toISOString(), ...value };
  entries.push(entry);
  if (entries.length > 100) entries.shift();
  if (value.category) console.warn("Apprentice diagnostic", entry);
}
export function setServerRelease(version: string, revision?: string) {
  serverVersion = version; serverRevision = revision || "unknown";
}
export function diagnosticReport() {
  return { exportedAt: new Date().toISOString(), version: serverVersion, revision: serverRevision,
    online: navigator.onLine, embedded: window.self !== window.top, entries: [...entries] };
}
export function downloadDiagnostics() {
  const url = URL.createObjectURL(new Blob([JSON.stringify(diagnosticReport(), null, 2)], { type: "application/json" }));
  const a = document.createElement("a"); a.href = url; a.download = "apprentice-diagnostics.json"; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
