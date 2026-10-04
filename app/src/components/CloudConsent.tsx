import { Toggle } from "./Controls";
import { useApp, run } from "../stores";

/** Keep consent reachable from Map and Teach after a reload resets it to off. */
export function CloudConsent() {
  const cloud = useApp((s) => s.data?.cloud) || false;
  if (window.desktop.platform !== "web") return null;
  return <section className="panel cloud-consent">
    <Toggle label="Use AI for this workflow" checked={cloud} onChange={(enabled) => run(() => useApp.getState().command("cloud", { enabled }))} />
    <p className="small muted">Shares this workflow's notes and relevant context with OpenAI. While recording, selected screenshots are also sent for analysis.</p>
  </section>;
}
