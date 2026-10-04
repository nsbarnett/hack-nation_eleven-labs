import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";

test("failed requests identify their operation and export a private-content-free diagnostic log", async ({ page }) => {
  await page.goto("/");
  await page.evaluate(async () => {
    await window.desktop.command("new", { title: "Diagnostics fixture" });
    await window.desktop.command("note", { text: "PRIVATE-EXPERT-NOTE" });
  });
  await page.getByRole("navigation").getByRole("button", { name: "Work Map", exact: true }).click();
  let calls = 0;
  await page.route("**/api/command", (route) => {
    if (route.request().postDataJSON().name === "build-map") { calls++; return route.abort("failed"); }
    return route.continue();
  });
  await page.getByRole("button", { name: "Build from evidence", exact: true }).click();
  const error = page.getByRole("alert");
  await expect(error).toContainText("Build Work Map failed");
  await expect(error).toContainText("Request ID:");
  expect(calls).toBe(1);
  const downloaded = page.waitForEvent("download");
  await error.getByRole("button", { name: "Download diagnostic log" }).click();
  const file = await downloaded;
  const text = await readFile((await file.path())!, "utf8");
  const report = JSON.parse(text);
  expect(report.version).toBe("0.5.0");
  const failure = report.entries.find((r: any) => r.category === "network" && r.operation === "Build Work Map");
  expect(failure.endpoint).toBe("/api/command");
  expect(failure.requestId).toMatch(/^[0-9a-f]{32}$/);
  expect(text).not.toContain("PRIVATE-EXPERT-NOTE");
  expect(text).not.toContain("Diagnostics fixture");
  await page.screenshot({ path: "../.artifacts/request-diagnostics.png", fullPage: true });
});
