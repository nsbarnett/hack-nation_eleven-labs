import { test, expect } from "@playwright/test";
import { readdirSync } from "node:fs";
const worker =
  "/assets/" +
  readdirSync("dist/assets").find((f) => f.startsWith("processor.worker-"));

test("local OCR detects an identifier and transmits neither the image nor OCR text", async ({
  page,
}) => {
  test.setTimeout(90000);
  const requests: string[] = [];
  page.on("request", (r) => requests.push(r.url()));
  await page.goto("/");
  const result = await page.evaluate(async (url) => {
    const canvas = document.createElement("canvas");
    canvas.width = 800;
    canvas.height = 160;
    const c = canvas.getContext("2d")!;
    c.fillStyle = "white";
    c.fillRect(0, 0, 800, 160);
    c.fillStyle = "black";
    c.font = "30px Arial";
    c.fillText("Contact: person@example.com", 25, 80);
    const blob = await new Promise<Blob>((r) =>
      canvas.toBlob((b) => r(b!), "image/png"),
    );
    return await new Promise<any>((resolve, reject) => {
      const worker = new Worker(url, { type: "module" });
      worker.onmessage = ({ data }) => {
        if (data.type === "error") {
          worker.terminate();
          reject(data.message);
        }
        if (data.type === "detected") {
          worker.terminate();
          resolve(data);
        }
      };
      worker.onerror = reject;
      worker.postMessage({ op: "detect", blob });
    });
  }, worker);
  expect(
    result.findings.some((f: any) => f.category === "Possible email"),
  ).toBe(true);
  expect(JSON.stringify(result)).not.toContain("person@");
  expect(
    requests.every((url) => url.startsWith("http://127.0.0.1:3001/")),
  ).toBe(true);
  expect(requests.some((url) => url.includes("/ocr/eng.traineddata.gz"))).toBe(
    true,
  );
});

test("exported WebM contains timed opaque covers, including moving keyframes", async ({
  page,
}) => {
  test.setTimeout(90000);
  await page.route('**/__test-codec-worker.js', route => route.fulfill({
    contentType: 'text/javascript',
    body: `self.VideoEncoder = undefined; await import(${JSON.stringify(worker)}); self.postMessage({type:'ready'});`,
  }));
  await page.goto("/");
  const result = await page.evaluate(async (workerURL) => {
    const job = (data: any) =>
      new Promise<any>((resolve, reject) => {
        const w = new Worker(workerURL, { type: "module" });
        w.onmessage = ({ data }) => {
          if (data.type === "done") {
            w.terminate();
            resolve(data);
          }
          if (data.type === "error") {
            w.terminate();
            reject(new Error(data.message));
          }
        };
        w.onerror = reject;
        w.postMessage(data);
      });
    const canvas = document.createElement("canvas");
    canvas.width = 320;
    canvas.height = 180;
    const context = canvas.getContext("2d")!;
    context.fillStyle = "white";
    context.fillRect(0, 0, 320, 180);
    const stream = canvas.captureStream(15),
      parts: Blob[] = [],
      recorder = new MediaRecorder(stream, {
        mimeType: "video/webm;codecs=vp8",
      });
    recorder.ondataavailable = (e) => parts.push(e.data);
    const stopped = new Promise<void>((r) => (recorder.onstop = () => r()));
    recorder.start();
    const timer = setInterval(() => {
      context.fillStyle = "white";
      context.fillRect(0, 0, 320, 180);
    }, 50);
    await new Promise((r) => setTimeout(r, 3100));
    recorder.stop();
    await stopped;
    clearInterval(timer);
    stream.getTracks().forEach((t) => t.stop());
    const blob = new Blob(parts, { type: "video/webm" }),
      segment = {
        name: "original.webm",
        start: 0,
        duration: 3.1,
        width: 320,
        height: 180,
      };
    await job({
      op: "render",
      blob,
      segment,
      name: "redacted.webm",
      guest: "pixel-test",
      session: "timing",
      revision: 1,
      cuts: [],
      covers: [
        {
          id: "cover",
          segment: segment.name,
          start: 0.75,
          end: 2.25,
          keyframes: [
            { time: 0.75, rect: { x: 0.1, y: 0.2, width: 0.2, height: 0.4 } },
            { time: 2, rect: { x: 0.6, y: 0.2, width: 0.2, height: 0.4 } },
          ],
        },
      ],
    });
    const db = await new Promise<IDBDatabase>((r) => {
      const q = indexedDB.open("apprentice-media-v1", 2);
      q.onsuccess = () => r(q.result);
    });
    const tx = db.transaction(["chunks", "assets"]);
    const chunks: any[] = await new Promise((r) => {
      const q = tx
        .objectStore("chunks")
        .index("asset")
        .getAll(["pixel-test", "timing", "redacted.webm"]);
      q.onsuccess = () => r(q.result);
    });
    const encoded = new Blob(
      chunks.sort((a, b) => a.index - b.index).map((c) => c.blob),
      { type: "video/webm" },
    );
    const values = [];
    for (const [time, x] of [
      [0.5, 0.2],
      [1, 0.3],
      [2.1, 0.7],
      [2.6, 0.7],
    ]) {
      const result = await job({ op: "frame", blob: encoded, segment, time });
      const frame = await createImageBitmap(result.blob),
        pixels = new OffscreenCanvas(frame.width, frame.height),
        c = pixels.getContext("2d")!;
      c.drawImage(frame, 0, 0);
      values.push(
        c.getImageData(
          Math.round(x * frame.width),
          Math.round(0.4 * frame.height),
          1,
          1,
        ).data[0],
      );
      frame.close();
    }
    // A full derivative budget must reject another output, without returning
    // raw video as a successful render.
    const full = db.transaction("assets", "readwrite");
    full
      .objectStore("assets")
      .put({
        guest: "pixel-test",
        session: "full",
        name: "existing.webm",
        type: "video/webm",
        size: 100_000_000,
        chunks: 0,
        partial: false,
        purpose: "redacted",
      });
    await new Promise<void>((r) => (full.oncomplete = () => r()));
    let quota = "";
    try {
      await job({
        op: "render",
        blob,
        segment,
        name: "blocked.webm",
        guest: "pixel-test",
        session: "full",
        revision: 1,
        cuts: [],
        covers: [],
      });
    } catch (error) {
      quota = String(error);
    }
    let invalid = "";
    try {
      await job({
        op: "render",
        blob: new Blob(["not a video"]),
        segment,
        name: "invalid.webm",
        guest: "pixel-test",
        session: "invalid",
        revision: 1,
        cuts: [],
        covers: [],
      });
    } catch (error) {
      invalid = String(error);
    }
    // A worker without WebCodecs encoding simulates an unsupported browser.
    const unsupported = await new Promise<string>((resolve, reject) => {
      const w = new Worker('/__test-codec-worker.js', { type: 'module' });
      w.onmessage = ({ data }) => {
        if (data.type === 'ready') w.postMessage({ op: 'render', blob, segment, name: 'unsupported.webm', guest: 'pixel-test', session: 'unsupported', revision: 1, cuts: [], covers: [] });
        if (data.type === 'done') { w.terminate(); reject(new Error('Unsupported encoding must not produce an export.')); }
        if (data.type === 'error') { w.terminate(); resolve(data.message); }
      };
      w.onerror = event => reject(new Error(`Unsupported-codec worker: ${event.message}`));
    });
    return { values, bytes: encoded.size, quota, invalid, unsupported };
  }, worker);
  expect(result.bytes).toBeGreaterThan(0);
  expect(result.values[0]).toBeGreaterThan(235);
  expect(result.values[1]).toBeLessThan(30);
  expect(result.values[2]).toBeLessThan(30);
  expect(result.values[3]).toBeGreaterThan(235);
  expect(result.quota).toContain("100 MB");
  expect(result.invalid.length).toBeGreaterThan(0);
  expect(result.unsupported).toContain('cannot encode');
});

test("manual covers and markers survive reload; unapproved media is not downloadable", async ({
  page,
}) => {
  test.setTimeout(90000);
  await page.addInitScript(() => {
    // Pause the render job at dispatch so cancellation is deterministic, while
    // retaining the real worker termination, IndexedDB and application cleanup.
    const NativeWorker = window.Worker;
    window.Worker = class extends NativeWorker {
      pending: ReturnType<typeof setTimeout> | undefined;
      postMessage(message: any, transfer: any = []) {
        if (message?.op === 'render') this.pending = setTimeout(() => super.postMessage(message, transfer), 10000);
        else super.postMessage(message, transfer);
      }
      terminate() { clearTimeout(this.pending); super.terminate(); }
    };
    navigator.mediaDevices.getDisplayMedia = async () => {
      const canvas = document.createElement("canvas");
      canvas.width = 640;
      canvas.height = 360;
      const c = canvas.getContext("2d")!;
      c.fillStyle = "#eee";
      c.fillRect(0, 0, 640, 360);
      const stream = canvas.captureStream(15),
        tick = setInterval(() => c.fillRect(0, 0, 2, 2), 50);
      stream
        .getTracks()[0]
        .addEventListener("ended", () => clearInterval(tick));
      return stream;
    };
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Start recording", exact: true })
    .click();
  await page.getByLabel("Workflow title").fill("Draft recovery test");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Start recording", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Pause", exact: true }),
  ).toBeVisible();
  await page.waitForTimeout(1300);
  await page.getByRole("button", { name: "Stop", exact: true }).click();
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Privacy Review", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Draw a cover" }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Draw a cover" }).click();
  await page.locator(".review-stage").scrollIntoViewIfNeeded();
  const stage = await page.locator(".review-stage").boundingBox();
  await page.mouse.move(stage!.x + 35, stage!.y + 35);
  await page.mouse.down();
  await page.mouse.move(stage!.x + 200, stage!.y + 100, { steps: 5 });
  await page.mouse.up();
  await expect(page.getByLabel("Cover end")).toBeVisible();
  await page.getByRole("button", { name: "Add marker here" }).click();
  await expect(
    page.getByRole("button", { name: /Manual review marker/ }).first(),
  ).toBeVisible();
  await page.reload();
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Privacy Review", exact: true })
    .click();
  await expect(page.getByLabel("Selected cover").locator("option")).toHaveCount(
    2,
  );
  await expect(
    page.getByRole("button", { name: /Manual review marker/ }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Use drawn cover" }).click();
  await expect(page.getByText(/0 unresolved suggestions/)).toBeVisible();
  await page.getByRole('button', { name: 'Render redacted copy' }).click();
  await page.getByRole('button', { name: 'Cancel processing' }).click();
  await expect(page.getByRole('alert')).toContainText('canceled');
  await expect(page.getByLabel('Selected cover').locator('option')).toHaveCount(2);
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Library", exact: true })
    .click();
  await expect(page.getByText("Open video", { exact: true })).toHaveCount(0);
  const snapshot = await (await page.request.get("/api/state")).json();
  expect(snapshot.session.privacy.status).toBe("unreviewed");
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Privacy Review", exact: true })
    .click();
  await page.screenshot({
    path: "../.artifacts/privacy-review.png",
    fullPage: true,
  });
});
