import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/web",
  workers: 1,
  timeout: 60000,
  expect: { timeout: 15000 },
  reporter: "list",
  use: { baseURL: process.env.WEB_TEST_URL || "http://127.0.0.1:3001", channel: "msedge", headless: true, screenshot: "only-on-failure" },
});
