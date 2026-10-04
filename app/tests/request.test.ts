import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { hostedRequest } from "../src/web/request";
import { diagnosticReport } from "../src/web/diagnostics";

beforeEach(() => {
  vi.stubGlobal("navigator", { onLine: true });
  vi.stubGlobal("window", { self: 1, top: 1 });
  vi.spyOn(console, "warn").mockImplementation(() => {});
});
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

test("network failure identifies the action and logs no request contents or IDs from query strings", async () => {
  const fetcher = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
  vi.stubGlobal("fetch", fetcher);
  await expect(hostedRequest("command", { name: "note", data: { text: "CONFIDENTIAL-NOTE" }, sessionId: "PRIVATE-WORKFLOW" }))
    .rejects.toThrow(/Save note or answer failed.*Request ID: [0-9a-f]{32}/);
  expect(fetcher).toHaveBeenCalledTimes(1); // Never replay a mutation with an unknown outcome.
  const record = diagnosticReport().entries.at(-1)!;
  expect(record).toMatchObject({ category: "network", method: "POST", endpoint: "/api/command" });
  expect(JSON.stringify(record)).not.toMatch(/CONFIDENTIAL|PRIVATE/);
  await expect(hostedRequest("reviewed-frame?sessionId=PRIVATE-WORKFLOW&id=PRIVATE-FRAME", undefined, new Uint8Array([1, 2])))
    .rejects.toThrow("Analyze approved frame failed");
  expect(diagnosticReport().entries.at(-1)!.endpoint).toBe("/api/reviewed-frame");
});

test("HTML proxy failures retain status and a correlated request ID", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>private proxy response</html>", {
    status: 503, headers: { "X-Apprentice-Request-ID": "a".repeat(32) },
  })));
  await expect(hostedRequest("state")).rejects.toThrow(`Refresh workspace failed (HTTP 503). The server or its provider is unavailable. Check the server logs and retry. Request ID: ${"a".repeat(32)}.`);
  expect(diagnosticReport().entries.at(-1)).toMatchObject({ status: 503, requestId: "a".repeat(32), category: "http" });
});

test("offline and interrupted response bodies have actionable errors", async () => {
  vi.stubGlobal("navigator", { onLine: false });
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
  await expect(hostedRequest("state")).rejects.toThrow("This browser is offline");
  vi.stubGlobal("navigator", { onLine: true });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, headers: new Headers(), json: async () => { throw new TypeError("stream interrupted"); } }));
  await expect(hostedRequest("state")).rejects.toThrow("connection was interrupted");
  expect(diagnosticReport().entries.at(-1)).toMatchObject({ status: 200, category: "network" });
});

test("timeouts identify the operation and invalid JSON is distinguished", async () => {
  vi.useFakeTimers();
  vi.stubGlobal("fetch", vi.fn((_url, options) => new Promise((_resolve, reject) => {
    options.signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
  })));
  const result = expect(hostedRequest("speech", { text: "private question" }, undefined, true)).rejects.toThrow("Play reviewer voice failed. The request timed out after 60 seconds.");
  await vi.advanceTimersByTimeAsync(60000);
  await result;
  expect(diagnosticReport().entries.at(-1)!.category).toBe("timeout");
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("not json")));
  await expect(hostedRequest("state")).rejects.toThrow("unreadable response");
});

test("successful JSON and audio requests are logged without their content", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(Response.json({ ok: true }))
    .mockResolvedValueOnce(new Response(new Uint8Array([1, 2, 3]))));
  expect(await hostedRequest("state")).toEqual({ ok: true });
  expect(await hostedRequest("speech", { text: "private question" }, undefined, true)).toEqual(new Uint8Array([1, 2, 3]));
  expect(diagnosticReport().entries.at(-1)!.event).toBe("request_completed");
  expect(JSON.stringify(diagnosticReport())).not.toContain("private question");
});
