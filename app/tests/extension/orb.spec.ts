import { test, expect, chromium } from "@playwright/test";
import { cp, mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

test("orb stays mounted through toggles, dragging, status updates and reconnect", async () => {
  // Test-only manifest pregrants host access; the shipped package requires an
  // explicit options-page permission prompt. No synthetic data is bundled.
  const folder = resolve("../.artifacts/extension-test");
  await mkdir(folder, { recursive: true });
  await cp("../release/extension/unpacked", folder, { recursive: true });
  const manifest = JSON.parse(
    await readFile(folder + "/manifest.json", "utf8"),
  );
  manifest.host_permissions = ["https://*/*", "http://*/*"];
  await writeFile(folder + "/manifest.json", JSON.stringify(manifest));
  const context = await chromium.launchPersistentContext("", {
    channel: process.env.EXTENSION_CHANNEL || "msedge",
    headless: true,
    viewport: { width: 1280, height: 900 },
    args: [
      `--disable-extensions-except=${folder}`,
      `--load-extension=${folder}`,
    ],
  });
  try {
    const worker =
      context.serviceWorkers()[0] ||
      (await context.waitForEvent("serviceworker"));
    const id = new URL(worker.url()).hostname;
    const options = await context.newPage();
    await options.goto(`chrome-extension://${id}/options.html`);
    await options.getByLabel("Apprentice origin").fill("http://127.0.0.1:3001");
    await options.getByRole("button").click();
    await expect(options.getByRole("status")).toContainText(
      "Connected origin saved",
    );
    const app = await context.newPage();
    await app.addInitScript(() => {
      navigator.mediaDevices.getDisplayMedia = async () => {
        const canvas = document.createElement("canvas");
        canvas.width = 320;
        canvas.height = 180;
        const c = canvas.getContext("2d")!;
        c.fillStyle = "#eee";
        c.fillRect(0, 0, 320, 180);
        const timer = setInterval(() => c.fillRect(0, 0, 2, 2), 100),
          stream = canvas.captureStream(15);
        stream
          .getTracks()[0]
          .addEventListener("ended", () => clearInterval(timer));
        return stream;
      };
    });
    await app.goto("http://127.0.0.1:3001");
    await expect(
      app.getByText("Your first workflow starts here"),
    ).toBeVisible();
    const host = await context.newPage();
    await host.route("http://example.test/**", (route) =>
      route.fulfill({
        contentType: "text/html",
        body: '<!doctype html><html><body><button id="underneath">Host page button</button></body></html>',
      }),
    );
    await host.goto("http://example.test/");
    await expect
      .poll(
        () =>
          host.frames().filter((f) => f.url().includes("surface.html")).length,
      )
      .toBe(3);
    const orb = host.frames().find((f) => f.url().endsWith("#orb"))!,
      bar = host.frames().find((f) => f.url().endsWith("#bar"))!,
      card = host.frames().find((f) => f.url().endsWith("#card"))!;
    const button = orb.getByRole("button");
    const originalBox = await button.boundingBox();
    await button.click();
    await expect(
      bar.getByRole("button", { name: "Record", exact: true }),
    ).toBeEnabled();
    for (let i = 0; i < 20; i++) await button.click({ force: true });
    expect(await button.boundingBox()).toEqual(originalBox);
    expect(
      host.frames().filter((f) => f.url().includes("surface.html")).length,
    ).toBe(3);
    await bar.getByRole("button", { name: "Record", exact: true }).click();
    await app.getByLabel("Workflow title").fill("Extension test recording");
    await app
      .getByRole("dialog")
      .getByRole("button", { name: "Start recording", exact: true })
      .click();
    await expect(
      bar.getByRole("button", { name: "Stop", exact: true }),
    ).toBeEnabled();
    await expect(bar.locator(".status")).toContainText("Recording locally");
    await bar.getByRole("button", { name: "Context", exact: true }).click();
    await card
      .getByLabel("Context or answer")
      .fill("Context submitted by the expert.");
    await card.getByRole("button", { name: "Send", exact: true }).click();
    await expect(
      app.getByText("Context submitted by the expert."),
    ).toBeVisible();
    await card.getByRole("button", { name: "Close question" }).click();
    await button.focus();
    await button.press("Alt+ArrowLeft");
    expect((await button.boundingBox())!.x).toBeLessThan(originalBox!.x);
    const beforeDrag = await button.boundingBox();
    await host.mouse.move(beforeDrag!.x + 25, beforeDrag!.y + 25);
    await host.mouse.down();
    await host.mouse.move(beforeDrag!.x - 100, beforeDrag!.y - 100, {
      steps: 10,
    });
    await host.mouse.up();
    await expect(button).toHaveAttribute("aria-expanded", "true"); // A drag does not toggle.
    await host.getByRole("button", { name: "Host page button" }).click(); // Outside surfaces remains clickable.
    await bar.getByRole("button", { name: "Stop", exact: true }).click();
    await expect(
      bar.getByRole("button", { name: "Record", exact: true }),
    ).toBeEnabled();
    await app.reload();
    await expect(
      bar.getByRole("button", { name: "Record", exact: true }),
    ).toBeEnabled();
    const position = await button.boundingBox();
    await host.reload();
    await expect
      .poll(() => host.frames().filter((f) => f.url().endsWith("#orb")).length)
      .toBe(1);
    const returned = host
      .frames()
      .find((f) => f.url().endsWith("#orb"))!
      .getByRole("button");
    expect(await returned.boundingBox()).toEqual(position);
    await host.screenshot({ path: "../.artifacts/extension-orb.png" });
    await app.close();
    const newBar = host.frames().find((f) => f.url().endsWith("#bar"))!;
    await returned.click();
    await expect(
      newBar.getByRole("button", { name: "Record", exact: true }),
    ).toBeDisabled();
    await expect(newBar.locator(".status")).toContainText("Disconnected");
  } finally {
    await context.close();
  }
});
