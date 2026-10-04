import {
  test,
  expect,
  _electron as electron,
  type ElectronApplication,
} from "@playwright/test";
import { mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
let desktop: ElectronApplication;
let data: string;
async function mainPage() {
  await expect
    .poll(() =>
      desktop.windows().some((page) => page.url().endsWith("/index.html")),
    )
    .toBe(true);
  return desktop.windows().find((page) => page.url().endsWith("/index.html"))!;
}
test.beforeEach(async () => {
  data = await mkdtemp(path.join(os.tmpdir(), "apprentice-electron-"));
  desktop = await electron.launch({
    executablePath: process.env.APPRENTICE_EXECUTABLE,
    args: process.env.APPRENTICE_EXECUTABLE ? [] : [path.resolve(".")],
    env: {
      ...process.env,
      APPRENTICE_DATA_DIR: data,
      OPENAI_API_KEY: "",
      ELEVENLABS_API_KEY: "",
    },
  });
});
test.afterEach(async () => {
  await desktop?.close();
  await rm(data, { recursive: true, force: true });
});
test("empty desktop, real note persistence, overlay and white theme", async () => {
  const page = await mainPage();
  page.on("pageerror", (error) =>
    console.error("Renderer error:", error.message),
  );
  await expect(
    page.getByRole("heading", { name: /Make experience/ }),
  ).toBeVisible();
  await expect(page.getByText("Your first workflow starts here")).toBeVisible();
  expect(
    await page.evaluate(() =>
      getComputedStyle(document.documentElement)
        .getPropertyValue("--background")
        .trim(),
    ),
  ).toBe("#fff");
  await page.screenshot({ path: "../.artifacts/electron-home.png" });
  await page.evaluate(() =>
    window.desktop.command("new", {
      title: "User-created test workflow",
      context: "User supplied context",
    }),
  );
  await page.getByRole("button", { name: "Record", exact: true }).click();
  await page
    .getByRole("textbox", { name: "Add a note or answer" })
    .fill("Expert-authored note for persistence testing.");
  await page.getByRole("button", { name: "Send note" }).click();
  await page.screenshot({ path: "../.artifacts/electron-note.png" });
  await expect(
    page.getByText("Expert-authored note for persistence testing."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Library", exact: true }).click();
  await expect(
    page.getByText("Expert-authored note for persistence testing."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await expect(page.getByText("Not configured").first()).toBeVisible();
  const overlay = desktop.windows().find((w) => w.url().endsWith("#overlay"))!;
  await expect(
    overlay.getByRole("button", { name: "Expand assistant" }),
  ).toBeVisible();
  await overlay.getByRole("button", { name: "Expand assistant" }).click();
  await expect(
    overlay.getByRole("button", { name: "Context", exact: true }),
  ).toBeVisible();
  await expect
    .poll(async () =>
      overlay
        .locator(".orb-toolbar")
        .evaluate((el) => el.getBoundingClientRect().width),
    )
    .toBeGreaterThan(280);
  await overlay.screenshot({ path: "../.artifacts/electron-overlay.png" });
  await overlay.getByRole("button", { name: "Context", exact: true }).click();
  await expect(
    page.getByRole("textbox", { name: "Add a note or answer" }),
  ).toBeFocused();
  const state = await page.evaluate(() => window.desktop.state());
  expect(state.session?.evidence).toHaveLength(1);
});
test("real screen capture survives navigation, pause releases tracks, stop saves media", async () => {
  const page = await mainPage();
  await expect(
    page.getByRole("heading", { name: /Make experience/ }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Start recording", exact: true })
    .click();
  await page
    .getByPlaceholder("Name the task you are documenting")
    .fill("Desktop capture acceptance");
  await page
    .getByRole("button", { name: "Choose source", exact: true })
    .click();
  await expect(page.locator(".source").first()).toBeVisible();
  await page.locator(".source").first().click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Start recording", exact: true })
    .click();
  await expect(page.getByText("Recording", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Home", exact: true }).click();
  await expect
    .poll(async () =>
      page.evaluate(async () => (await window.desktop.state()).media.state),
    )
    .toBe("recording");
  const beforeMinimize = await page.evaluate(
    async () => (await window.desktop.state()).media.duration,
  );
  await desktop.evaluate(({ BrowserWindow }) =>
    BrowserWindow.getAllWindows()[0].minimize(),
  );
  await expect
    .poll(async () =>
      page.evaluate(async () => (await window.desktop.state()).media.duration),
    )
    .toBeGreaterThan(beforeMinimize + 1);
  await desktop.evaluate(({ BrowserWindow }) => {
    const main = BrowserWindow.getAllWindows()[0];
    main.restore();
    main.show();
    main.focus();
  });
  await page.getByRole("button", { name: "Record", exact: true }).click();
  await page.getByRole("button", { name: "Pause", exact: true }).click();
  await expect(page.getByText("Paused", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Resume", exact: true }).click();
  await expect(page.getByText("Recording", { exact: true })).toBeVisible();
  await expect
    .poll(async () =>
      page.evaluate(
        async () =>
          (await window.desktop.state()).session?.evidence.length || 0,
      ),
    )
    .toBeGreaterThan(0);
  await page.getByRole("button", { name: "Stop", exact: true }).click();
  await expect(
    page.getByText("Ready to record", { exact: true }),
  ).toBeVisible();
  const state = await page.evaluate(() => window.desktop.state());
  expect(state.session?.recordings).toHaveLength(2);
  await page.screenshot({ path: "../.artifacts/electron-record.png" });
});
