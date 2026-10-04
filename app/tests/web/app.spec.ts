import { test, expect, type Page } from "@playwright/test";

async function captureFixture(page: Page, denied = false) {
  await page.addInitScript((deny) => {
    navigator.mediaDevices.getDisplayMedia = async () => {
      if (deny) throw new DOMException("Permission denied", "NotAllowedError");
      const canvas = document.createElement("canvas");
      canvas.width = 640; canvas.height = 360;
      const ctx = canvas.getContext("2d")!;
      ctx.fillStyle = "#eee"; ctx.fillRect(0, 0, 640, 360);
      ctx.fillStyle = "#111"; ctx.fillText("Browser test capture fixture", 30, 50);
      const stream = canvas.captureStream(15);
      const timer = setInterval(() => { ctx.fillRect(0, 0, 1, 1); }, 100);
      stream.getVideoTracks()[0].addEventListener("ended", () => clearInterval(timer));
      return stream;
    };
  }, denied);
}
async function createRecording(page: Page, title: string) {
  await page.getByRole("button", { name: "Start recording", exact: true }).click();
  await page.getByLabel("Workflow title").fill(title);
  await page.getByRole("switch", { name: "Enable cloud analysis for this session" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Start recording", exact: true }).click();
  await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeVisible();
}

test("empty first launch and permission denial do not invent a workflow", async ({ page }) => {
  await captureFixture(page, true);
  await page.goto("/");
  await expect(page.getByText("Your first workflow starts here")).toBeVisible();
  await page.getByRole("button", { name: "Start recording", exact: true }).click();
  await page.getByLabel("Workflow title").fill("Permission denied task");
  await page.getByRole("dialog").getByRole("button", { name: "Start recording", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Permission denied");
  const snapshot = await (await page.request.get("/api/state")).json();
  expect(snapshot.sessions).toEqual([]);
});

test("capture survives navigation; local media, debrief, map review and teach complete", async ({ page }) => {
  await captureFixture(page);
  const videoUploads: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && /segment|chunk|video/.test(request.url())) videoUploads.push(request.url());
  });
  await page.goto("/");
  await createRecording(page, "Browser acceptance workflow");
  await page.getByLabel("Add a note or answer").fill("The expert checks the task before proceeding because incomplete input must be corrected.");
  await page.getByRole("button", { name: "Send note" }).click();
  await page.getByRole("navigation").getByRole("button", { name: "Home", exact: true }).click();
  await page.getByRole("navigation").getByRole("button", { name: "Record", exact: true }).click();
  await page.getByRole("button", { name: "Pause", exact: true }).click();
  await expect(page.getByRole("button", { name: "Resume", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Resume", exact: true }).click();
  await page.getByRole("button", { name: "Stop", exact: true }).click();
  await page.getByRole("navigation").getByRole("button", { name: "Library", exact: true }).click();
  await expect(page.getByText("Open video").first()).toBeVisible();
  await page.getByText("Open video").first().click();
  await expect(page.getByRole("link", { name: "Download recording" })).toHaveAttribute("href", /^blob:/);
  await page.keyboard.press("Escape");
  expect(videoUploads).toEqual([]);
  await page.getByRole("navigation").getByRole("button", { name: "Debrief", exact: true }).click();
  await page.getByRole("button", { name: "Ask the next question" }).click();
  await expect(page.getByText("What makes this check necessary?").first()).toBeVisible();
  await page.getByLabel("Add a note or answer").fill("It prevents proceeding with incomplete input.");
  await page.getByRole("button", { name: "Send note" }).click();
  await page.getByRole("navigation").getByRole("button", { name: "Work Map", exact: true }).click();
  await page.getByRole("button", { name: "Build from evidence" }).click();
  await expect(page.getByRole("heading", { name: "Review the work" })).toBeVisible();
  await page.getByRole("button", { name: "Review", exact: true }).click();
  await page.getByRole("combobox").selectOption("verified");
  await page.getByRole("button", { name: "Save review" }).click();
  await page.getByRole("button", { name: "Confirm reviewed map" }).click();
  await page.getByRole("navigation").getByRole("button", { name: "Teach", exact: true }).click();
  await page.getByRole("button", { name: "Generate practice" }).click();
  await page.getByLabel("Answer exercise 1").fill("Review the input and ask the expert if it is incomplete.");
  await page.getByRole("button", { name: "Get feedback" }).click();
  await expect(page.getByText("Your answer follows the confirmed review step.").first()).toBeVisible();
  await page.reload();
  await page.getByRole("navigation").getByRole("button", { name: "Teach", exact: true }).click();
  await expect(page.getByText("1 of 1 answered")).toBeVisible();
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Delete open workflow & media" }).click();
  await page.getByRole("navigation").getByRole("button", { name: "Home", exact: true }).click();
  await expect(page.getByText("Your first workflow starts here")).toBeVisible();
});

test("another browser has an empty isolated workspace and APIs reject foreign IDs", async ({ page, browser }) => {
  await captureFixture(page);
  await page.goto("/");
  await createRecording(page, "Isolated workflow");
  await page.getByRole("button", { name: "Stop", exact: true }).click();
  const first = await (await page.request.get("/api/state")).json();
  const other = await browser.newContext();
  const second = await other.newPage();
  await second.goto(page.url());
  await expect(second.getByText("Your first workflow starts here")).toBeVisible();
  const response = await second.request.post(new URL("/api/command", page.url()).href, {
    headers: { Origin: new URL(page.url()).origin, "X-Apprentice-Client": "web" },
    data: { name: "open", data: { id: first.session.id } },
  });
  expect(response.status()).toBe(404);
  await other.close();
});
