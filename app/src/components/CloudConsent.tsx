import { useApp } from "../stores";

/** Explain the browser's processing boundary without a second activation gate. */
export function CloudConsent() {
  const available = useApp((s) => s.data?.credentials.openai);
  if (window.desktop.platform !== "web") return null;
  return <section className="panel cloud-consent">
    <p className="small muted">{available ? "AI uses your workflow notes and context. Screenshots are analyzed only after privacy approval and your Analyze action." : "The AI connection is unavailable. Contact the app owner; your saved work is retained."}</p>
  </section>;
}
