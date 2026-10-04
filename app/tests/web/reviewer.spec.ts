import { test, expect, type Page } from "@playwright/test";

async function start(page: Page, title: string) {
  await page.addInitScript(() => {
    navigator.mediaDevices.getDisplayMedia = async () => {
      const canvas = document.createElement("canvas"); canvas.width = 640; canvas.height = 360;
      const c = canvas.getContext("2d")!; c.fillStyle = "white"; c.fillRect(0, 0, 640, 360);
      const began = Date.now();
      const draw = () => { c.fillStyle = "white"; c.fillRect(0, 0, 640, 360); c.fillStyle = "black"; c.font = "28px Arial"; c.fillText(`Cost center: ${Date.now() - began < 5000 ? "4711" : "0400"}`, 30, 80); };
      draw();
      const stream = canvas.captureStream(15);
      const timer = setInterval(draw, 100);
      stream.getVideoTracks()[0].addEventListener("ended", () => clearInterval(timer));
      return stream;
    };
    (window as any).Audio = class {
      src: string; onended: (() => void) | null = null;
      constructor(src: string) { this.src = src; }
      async play() { setTimeout(() => this.onended?.(), 150); }
      pause() {}
    };
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Start recording", exact: true }).click();
  await page.getByLabel("Workflow title").fill(title);
  await expect(page.getByRole("switch", { name: /cloud analysis/i })).toHaveCount(0);
  await page.getByRole("dialog").getByRole("button", { name: "Start recording", exact: true }).click();
  await expect(page.getByRole("button", { name: "Stop", exact: true })).toBeVisible();
}

for (const mode of ["Text only", "Voice only", "Text and voice"]) {
  test(`note interjection uses ${mode} and does not upload screens`, async ({ page }) => {
    let spoken = 0;
    const uploads: string[] = [];
    page.on("request", (r) => { if (/\/api\/(frame|reviewed-frame)/.test(r.url())) uploads.push(r.url()); });
    await page.route("**/api/state", async (route) => {
      const response = await route.fetch(); const body = await response.json();
      body.credentials.elevenlabs = true;
      await route.fulfill({ response, json: body });
    });
    await page.route("**/api/speech", (route) => { spoken++; return route.fulfill({ contentType: "audio/mpeg", body: Buffer.from([1, 2, 3]) }); });
    await start(page, "Reviewer presentation fixture");
    await page.getByRole("switch", { name: "Allow reviewer interjections" }).click();
    await page.getByRole("radio", { name: mode, exact: true }).check();
    await page.getByLabel("Add a note or answer").fill("I changed the classification for the interjection fixture.");
    await page.getByRole("button", { name: "Send note" }).click();
    const popup = page.getByRole("complementary", { name: "Reviewer question" });
    await expect(popup).toBeVisible({ timeout: 20000 });
    if (mode === "Voice only") {
      await expect(popup.getByRole("button", { name: "Show question text" })).toBeVisible();
      await expect(popup).not.toContainText("What made you choose");
    } else await expect(popup).toContainText("What made you choose");
    if (mode === "Text only") expect(spoken).toBe(0);
    else await expect.poll(() => spoken).toBe(1);
    await page.getByRole("navigation").getByRole("button", { name: "Home", exact: true }).click();
    await expect(popup).toBeVisible();
    await expect(page.getByRole("heading", { name: "Make experience something you can share." })).toBeVisible();
    expect(uploads).toEqual([]);
    await page.screenshot({ path: `../.artifacts/reviewer-${mode.replaceAll(" ", "-")}.png`, fullPage: true });
    await popup.getByRole("button", { name: "Later", exact: true }).click();
    await expect(popup).toBeHidden();
    await page.getByRole("navigation").getByRole("button", { name: "Record", exact: true }).click();
    await page.getByRole("button", { name: "Stop", exact: true }).click();
    expect(spoken).toBe(mode === "Text only" ? 0 : 1);
    await page.reload();
    await page.getByRole("navigation").getByRole("button", { name: "Record", exact: true }).click();
    await expect(page.getByRole("switch", { name: "Allow reviewer interjections" })).toBeChecked();
    await expect(page.getByRole("radio", { name: mode, exact: true })).toBeChecked();
  });
}

test("failed ElevenLabs speech exposes voice-only questions as text", async ({ page }) => {
  await page.route("**/api/state", async (route) => {
    const response = await route.fetch(); const body = await response.json();
    body.credentials.elevenlabs = true;
    await route.fulfill({ response, json: body });
  });
  await page.route("**/api/speech", (route) => route.fulfill({ status: 503, json: { detail: "Voice is temporarily unavailable." } }));
  await start(page, "Speech failure fixture");
  await page.getByRole("switch", { name: "Allow reviewer interjections" }).click();
  await page.getByRole("radio", { name: "Voice only", exact: true }).check();
  await page.getByLabel("Add a note or answer").fill("I changed the classification for the interjection fixture.");
  await page.getByRole("button", { name: "Send note" }).click();
  const popup = page.getByRole("complementary", { name: "Reviewer question" });
  await expect(popup).toContainText("Voice could not play", { timeout: 20000 });
  await expect(popup).toContainText("What made you choose");
  await page.getByRole("button", { name: "Stop", exact: true }).click();
});

test("context and Work Map processing stay visible across navigation", async ({ page }) => {
  await page.goto("/");
  await page.evaluate(async () => {
    await window.desktop.command("new", { title: "Processing feedback fixture" });
    await window.desktop.command("note", { text: "Review the input before proceeding in the processing feedback fixture." });
    await window.desktop.command("build-map");
  });
  const processing = page.locator(".processing-status");
  await expect(processing).toContainText("Evaluating context");
  await page.getByRole("navigation").getByRole("button", { name: "Workflows", exact: true }).click();
  await expect(processing).toBeVisible();
  await expect(processing).toContainText("Building process steps");
  await page.getByRole("navigation").getByRole("button", { name: "Work Map", exact: true }).click();
  await expect(processing).toBeHidden();
  await expect(page.getByRole("heading", { name: "Review the work" })).toBeVisible();
});

test("approved analysis surfaces one supported screen question and keeps its outcome after reload", async ({ page }) => {
  test.setTimeout(90000);
  let uploads = 0;
  page.on("request", (r) => { if (r.url().includes("/api/reviewed-frame")) uploads++; });
  await start(page, "Screen change fixture");
  await page.waitForTimeout(11000); // A real before/after capture within the unchanged two-frame budget.
  expect(uploads).toBe(0);
  await page.getByRole("button", { name: "Stop", exact: true }).click();
  await page.getByRole("navigation").getByRole("button", { name: "Privacy Review", exact: true }).click();
  await expect(page.getByRole("button", { name: "Render redacted copy" })).toBeEnabled();
  await page.getByRole("button", { name: "Render redacted copy" }).click();
  await expect(page.getByText(/Rendered copy .* covers are permanent/)).toBeVisible();
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Approve reviewed recording" }).click();
  await page.getByRole("button", { name: "Analyze approved frames" }).click();
  const popup = page.getByRole("complementary", { name: "Reviewer question" });
  await expect(popup).toContainText("You changed cost center from 4711 to 0400.");
  await expect(page.getByRole("button", { name: "Analyze approved frames" })).toBeEnabled();
  expect(uploads).toBe(2);
  const completed = await (await page.request.get("/api/state")).json();
  expect(completed.session.knowledge).toHaveLength(1);
  expect(completed.session.privacy.map_revision).toBe(completed.session.privacy.revision);
  await expect(page.getByRole("navigation").getByRole("button", { name: "Privacy Review", exact: true })).not.toContainText("Action needed");
  const first = (await (await page.request.get("/api/state")).json()).question.id;
  await popup.getByRole("button", { name: "Open Debrief" }).click();
  await expect(page.getByRole("heading", { name: "What should someone else know?", exact: true })).toBeVisible();
  await page.reload();
  await expect(popup).toBeVisible();
  expect((await (await page.request.get("/api/state")).json()).question.id).toBe(first);
  await popup.getByRole("button", { name: "Later", exact: true }).click();
  await page.getByRole("navigation").getByRole("button", { name: "Privacy Review", exact: true }).click();
  await page.getByRole("button", { name: "Analyze approved frames" }).click();
  await expect(page.getByRole("button", { name: "Analyze approved frames" })).toBeEnabled();
  await expect(popup).toBeHidden();
  expect(uploads).toBe(2);
  expect((await (await page.request.get("/api/state")).json()).session.evaluation.attempts).toHaveLength(1);
  await expect(page.getByRole("button", { name: "Open Debrief", exact: true })).toBeVisible();
});

test("deleting during local processing drains workers and removes drafts and media", async ({ page }) => {
  await page.addInitScript(() => {
    const NativeWorker = window.Worker;
    window.Worker = class extends NativeWorker {
      pending: ReturnType<typeof setTimeout> | undefined;
      postMessage(message: any, transfer: any = []) {
        if (message?.op === "render") this.pending = setTimeout(() => super.postMessage(message, transfer), 3000);
        else super.postMessage(message, transfer);
      }
      terminate() { clearTimeout(this.pending); super.terminate(); }
    };
  });
  await start(page, "Delete pending local job");
  await page.waitForTimeout(1300);
  await page.getByRole("button", { name: "Stop", exact: true }).click();
  const before = await (await page.request.get("/api/state")).json();
  await page.getByRole("navigation").getByRole("button", { name: "Privacy Review", exact: true }).click();
  await page.getByRole("button", { name: "Render redacted copy" }).click();
  await expect(page.locator(".processing-status")).toContainText("Rendering covers");
  await page.getByRole("navigation").getByRole("button", { name: "Workflows", exact: true }).click();
  await page.getByRole("button", { name: "Delete Delete pending local job", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Delete workflow", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeHidden();
  await expect(page.locator(".processing-status")).toBeHidden();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await page.waitForTimeout(3500); // A late worker must not recreate a review or derivative.
  const sizes = await page.evaluate(async ({ guest, session }) => {
    const db = await new Promise<IDBDatabase>((resolve) => { const r = indexedDB.open("apprentice-media-v1", 2); r.onsuccess = () => resolve(r.result); });
    const rows = await Promise.all(["assets", "chunks", "reviews"].map((store) => new Promise<any[]>((resolve) => {
      const r = db.transaction(store).objectStore(store).getAll(); r.onsuccess = () => resolve(r.result);
    })));
    db.close(); return rows.map((values) => values.filter((v) => v.guest === guest && v.session === session).length);
  }, { guest: before.guest, session: before.session.id });
  expect(sizes).toEqual([0, 0, 0]);
  expect((await (await page.request.get("/api/state")).json()).sessions).toEqual([]);
});

test("deleting an inactive workflow preserves the active one and retries failed local cleanup", async ({ page }) => {
  await page.goto("/");
  const target = await page.evaluate(async () => {
    await window.desktop.command("new", { title: "Delete selected" });
    const first = await window.desktop.state();
    await window.desktop.beginSegment({ start: 0, width: 640, height: 360 });
    await window.desktop.command("note", { text: "Target evidence" });
    await window.desktop.command("new", { title: "Keep active" });
    const db = await new Promise<IDBDatabase>((resolve) => { const req = indexedDB.open("apprentice-media-v1", 2); req.onsuccess = () => resolve(req.result); });
    const tx = db.transaction(["reviews"], "readwrite");
    tx.objectStore("reviews").put({ guest: first.guest, session: first.session!.id, revision: 0 });
    await new Promise<void>((resolve) => { tx.oncomplete = () => resolve(); });
    db.close();
    return { id: first.session!.id, guest: first.guest };
  });
  await page.getByRole("navigation").getByRole("button", { name: "Workflows", exact: true }).click();
  await page.getByRole("button", { name: "Delete Delete selected", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("textbox")).toHaveCount(0);
  await dialog.getByRole("button", { name: "Cancel" }).click();
  expect((await (await page.request.get("/api/state")).json()).sessions).toHaveLength(2);
  await page.getByRole("button", { name: "Delete Delete selected", exact: true }).click();
  await page.evaluate(() => {
    const original = IDBDatabase.prototype.transaction;
    let fail = true;
    IDBDatabase.prototype.transaction = function(names: string | string[], ...args: any[]) {
      if (fail && Array.isArray(names) && names.includes("chunks") && names.includes("reviews")) { fail = false; throw new Error("Simulated cleanup failure; retry deletion."); }
      return original.call(this, names, ...args);
    };
  });
  await dialog.getByRole("button", { name: "Delete workflow", exact: true }).click();
  await expect(dialog.getByRole("alert")).toContainText("Simulated cleanup failure");
  expect((await (await page.request.get("/api/state")).json()).session.title).toBe("Keep active");
  await dialog.getByRole("button", { name: "Delete workflow", exact: true }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByRole("alert")).toHaveCount(0);
  const retained = await page.evaluate(async ({ guest, id }) => {
    const db = await new Promise<IDBDatabase>((resolve) => { const req = indexedDB.open("apprentice-media-v1", 2); req.onsuccess = () => resolve(req.result); });
    const result = await new Promise((resolve) => { const req = db.transaction("reviews").objectStore("reviews").get([guest!, id]); req.onsuccess = () => resolve(req.result); });
    db.close(); return result;
  }, target);
  expect(retained).toBeUndefined();
  await page.reload();
  expect((await (await page.request.get("/api/state")).json()).cloud).toBe(true);
});

test("privacy actions are discoverable and bulk rejection never approves or uploads", async ({ page }) => {
  let uploads = 0;
  page.on("request", (r) => { if (r.url().includes("/api/reviewed-frame")) uploads++; });
  await start(page, "Privacy action guidance");
  await page.waitForTimeout(1400);
  await page.getByRole("button", { name: "Stop", exact: true }).click();
  const nav = page.getByRole("navigation").getByRole("button", { name: "Privacy Review", exact: true });
  await expect(nav).toContainText("Action needed");
  await page.getByRole("navigation").getByRole("button", { name: "Home", exact: true }).click();
  await expect(page.locator(".workflow-privacy-action")).toContainText("Review and approve");
  await page.getByRole("button", { name: "Review privacy", exact: true }).click();
  await expect(page.getByRole("button", { name: "Render redacted copy" })).toBeEnabled();
  await page.evaluate(async () => {
    const state = await window.desktop.state();
    const db = await new Promise<IDBDatabase>((resolve) => { const r = indexedDB.open("apprentice-media-v1", 2); r.onsuccess = () => resolve(r.result); });
    await new Promise<void>((resolve) => {
      const tx = db.transaction("reviews", "readwrite"), store = tx.objectStore("reviews");
      const r = store.get([state.guest!, state.session!.id]);
      r.onsuccess = () => { const draft = r.result; draft.markers = [0.1, 0.3].map((time, i) => ({ id: `synthetic-${i}`, segment: draft.segments[0].name, time, category: "Synthetic detection", decision: "pending" })); store.put(draft); };
      tx.oncomplete = () => resolve();
    });
    db.close();
    window.dispatchEvent(new CustomEvent("privacy-change", { detail: state.session!.id }));
  });
  await expect(page.getByRole("button", { name: "Render redacted copy" })).toBeDisabled();
  await expect(page.getByRole("checkbox")).toBeDisabled();
  await page.getByRole("button", { name: "Reject all suggestions", exact: true }).click();
  await expect(page.getByRole("button", { name: "Reopen", exact: true })).toHaveCount(2);
  await expect(page.getByRole("button", { name: "Render redacted copy" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Approve reviewed recording" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Analyze approved frames" })).toBeDisabled();
  expect(uploads).toBe(0);
  expect((await (await page.request.get("/api/state")).json()).session.privacy.status).toBe("unreviewed");
  const style = await page.getByRole("button", { name: "Render redacted copy" }).evaluate((el) => getComputedStyle(el).userSelect);
  expect(style).toBe("none");
  await page.getByRole("button", { name: "Reopen", exact: true }).first().click();
  await expect(page.getByRole("button", { name: "Render redacted copy" })).toBeDisabled();
  await page.getByRole("button", { name: "Reject all suggestions", exact: true }).click();
  await page.getByRole("button", { name: "Render redacted copy" }).click();
  await expect(page.getByRole("checkbox")).toBeEnabled();
  await page.screenshot({ path: "../.artifacts/privacy-flow-guidance.png", fullPage: true });
  await page.locator(".privacy-approve").screenshot({ path: "../.artifacts/privacy-review-actions.png" });
});
