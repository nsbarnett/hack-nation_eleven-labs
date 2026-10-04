import { validOrigin } from "./protocol";
const input = document.querySelector("input")!,
  status = document.querySelector("[role=status]")!;
void chrome.storage.local.get("origin").then((value) => {
  input.value = typeof value.origin === "string" ? value.origin : "";
});
document.querySelector("button")!.onclick = async () => {
  const origin = input.value.trim().replace(/\/$/, "");
  if (!validOrigin(origin)) {
    status.textContent =
      "Enter the exact HTTPS app origin, without a path. Localhost is allowed for development.";
    return;
  }
  // Request in the original user gesture, before storage/network awaits.
  const granted = await chrome.permissions.request({
    origins: ["https://*/*", "http://*/*"],
  });
  if (!granted) {
    status.textContent =
      "Website access was not granted. You can still use Apprentice in its tab.";
    return;
  }
  await chrome.storage.local.set({ origin });
  status.textContent =
    "Connected origin saved. Open or reload Apprentice and the websites where you want the orb.";
};
