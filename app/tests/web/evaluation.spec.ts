import { test, expect } from "@playwright/test";

test("evaluation dimensions, explicit gap review, and rule-graded practice persist", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Your first workflow starts here")).toBeVisible();
  await page.evaluate(async () => {
    await window.desktop.command("new", { title: "Structured evaluation workflow", cloud: true });
    await window.desktop.command("note", { text: "For EUR purchases at least 5000, choose CAPEX. Other currencies need expert review." });
  });
  await page.getByRole("navigation").getByRole("button", { name: "Debrief", exact: true }).click();
  const evaluation = page.getByRole("region", { name: "Knowledge evaluation" });
  await expect(evaluation.getByText("Answer sufficiency", { exact: true })).toBeVisible();
  await expect(evaluation.getByText("1 explanations awaiting assessment; 0 partial")).toBeVisible();
  await evaluation.getByText(/Review knowledge gaps/).click();
  await evaluation.getByRole("button", { name: "Review clarification" }).first().click();
  await evaluation.getByLabel("Expert clarification").fill("The rule applies to EUR purchases at least 5000. Other currencies remain outside its scope.");
  await evaluation.getByRole("button", { name: "Save expert review" }).click();
  await expect(evaluation.getByText("verified", { exact: true })).toBeVisible();

  await page.getByRole("navigation").getByRole("button", { name: "Work Map", exact: true }).click();
  await page.getByRole("button", { name: "Build from evidence" }).click();
  await expect(page.getByRole("heading", { name: "Classify at the threshold" })).toBeVisible();
  await page.getByRole("button", { name: "Review", exact: true }).click();
  const review = page.getByRole("dialog", { name: "Review this step" });
  await review.getByLabel("Review status").selectOption("verified");
  await review.getByRole("checkbox").check();
  await review.getByRole("button", { name: "Save review" }).click();
  await expect(page.getByText("Executable rule: reviewed for structured practice.")).toBeVisible();
  await page.screenshot({ path: "../.artifacts/evaluation-panel.png", fullPage: true });
  await page.getByRole("button", { name: "Confirm reviewed map" }).click();
  await page.getByRole("navigation").getByRole("button", { name: "Teach", exact: true }).click();
  await page.getByRole("button", { name: "Generate practice" }).click();
  await page.getByLabel("Exercise 1: category").fill("OPEX");
  await page.getByRole("button", { name: "Get feedback" }).click();
  await expect(page.getByText("Verified rule evaluation · warn")).toBeVisible();
  await page.getByLabel("Exercise 1: category").fill("CAPEX");
  await page.getByRole("button", { name: "Get feedback" }).click();
  await expect(page.getByText("Verified rule evaluation · ok")).toBeVisible();
  await page.screenshot({ path: "../.artifacts/evaluation-practice.png", fullPage: true });
  await page.reload();
  await page.getByRole("navigation").getByRole("button", { name: "Teach", exact: true }).click();
  await expect(page.getByText("Verified rule evaluation · ok")).toBeVisible();
});
