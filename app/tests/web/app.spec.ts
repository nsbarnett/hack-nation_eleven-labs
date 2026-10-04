import { test, expect, type Page, type WebSocketRoute } from "@playwright/test";

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
  test.setTimeout(180000);
  const videoUploads: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && /segment|chunk|video|api\/frame|api\/reviewed-frame/.test(request.url())) videoUploads.push(request.url());
  });
  await page.goto("/");
  await createRecording(page, "Browser acceptance workflow");
  await page.getByLabel("Add a note or answer").fill("The expert checks the task before proceeding because incomplete input must be corrected.");
  await page.getByRole("button", { name: "Send note" }).click();
  await page.getByRole("navigation").getByRole("button", { name: "Home", exact: true }).click();
  await page.getByRole("navigation").getByRole("button", { name: "Record", exact: true }).click();
  await page.waitForTimeout(1200);
  await page.getByRole("button", { name: "Pause", exact: true }).click();
  await expect(page.getByRole("button", { name: "Resume", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Resume", exact: true }).click();
  await page.waitForTimeout(1200);
  await page.getByRole("button", { name: "Stop", exact: true }).click();
  await page.getByRole("navigation").getByRole("button", { name: "Privacy Review", exact: true }).click();
  await expect(page.getByRole('button', { name: 'Render redacted copy' })).toBeEnabled({ timeout: 90000 });
  await page.getByRole('button', { name: 'Render redacted copy' }).click();
  await expect(page.getByText(/Rendered copy .* covers are permanent/)).toBeVisible();
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Approve reviewed recording' }).click();
  await expect(page.getByText('Approved. Library playback and downloads use the redacted copy.')).toBeVisible();
  await page.getByRole("navigation").getByRole("button", { name: "Library", exact: true }).click();
  await expect(page.getByText("Open video").first()).toBeVisible();
  await page.getByText("Open video").first().click();
  await expect(page.getByRole("link", { name: "Download recording" })).toHaveAttribute("href", /^blob:/);
  await page.keyboard.press("Escape");
  expect(videoUploads).toEqual([]);
  await page.getByRole('navigation').getByRole('button', { name: 'Privacy Review', exact: true }).click();
  await page.getByRole('button', { name: 'Analyze approved frames' }).click();
  await expect(page.locator('.processing-status')).toBeVisible();
  await page.getByRole('navigation').getByRole('button', { name: 'Workflows', exact: true }).click();
  await expect(page.locator('.processing-status')).toBeVisible();
  await page.getByRole('navigation').getByRole('button', { name: 'Privacy Review', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Analyze approved frames' })).toBeEnabled({ timeout: 90000 });
  await expect(page.getByText('Analysis complete. The current evidence does not support a new screen question. Add context or review the findings in Debrief.')).toBeVisible();
  expect(videoUploads.some(url => url.includes('/api/reviewed-frame'))).toBe(true);
  expect(videoUploads.every(url => url.includes('/api/reviewed-frame'))).toBe(true);
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
  await page.getByRole("button", { name: "Delete Browser acceptance workflow", exact: true }).click();
  const deletion = page.getByRole("dialog");
  await expect(deletion).toContainText("Browser acceptance workflow");
  await expect(deletion.getByRole("textbox")).toHaveCount(0);
  await deletion.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(deletion).toBeHidden();
  const preserved = await (await page.request.get("/api/state")).json();
  expect(preserved.session.title).toBe("Browser acceptance workflow");
  expect(preserved.session.evidence.length).toBeGreaterThan(0);
  await page.getByRole("button", { name: "Delete Browser acceptance workflow", exact: true }).click();
  await deletion.getByRole("button", { name: "Delete workflow", exact: true }).click();
  await expect(deletion).toBeHidden();
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

test("reconnection recovers recording even when the final stop request was lost", async ({ page }) => {
  await captureFixture(page);
  let connection: WebSocketRoute | undefined;
  await page.routeWebSocket("**/api/events", (socket) => {
    socket.connectToServer();
    connection = socket;
  });
  await page.goto("/");
  await createRecording(page, "Connection recovery task");
  await page.route("**/api/command", (route) => {
    const body = route.request().postDataJSON();
    return body.name === "recording" && body.data.state === "idle" ? route.abort("failed") : route.continue();
  });
  await connection!.close({ code: 1012, reason: "Disposable test interruption" });
  await expect.poll(async () => (await (await page.request.get("/api/state")).json()).recording).toBe("idle");
  const recovered = await (await page.request.get("/api/state")).json();
  expect(recovered.cloud).toBe(true);
  await page.unroute("**/api/command");
  await page.getByRole("navigation").getByRole("button", { name: "Home", exact: true }).click();
  await createRecording(page, "Recording after reconnection");
  await page.getByRole("button", { name: "Stop", exact: true }).click();
});
