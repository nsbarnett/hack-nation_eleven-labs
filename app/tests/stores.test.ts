import { beforeEach, expect, test, vi } from "vitest";
import { useApp } from "../src/stores";
beforeEach(() => {
  useApp.setState({ data: null, error: "", page: "Home" });
});
test("a delayed snapshot cannot replace newer session state", async () => {
  const state = vi
    .fn()
    .mockResolvedValueOnce({ sequence: 4, session: { id: "current" } })
    .mockResolvedValueOnce({ sequence: 3, session: { id: "old" } });
  vi.stubGlobal("window", { desktop: { state } });
  await useApp.getState().refresh();
  await useApp.getState().refresh();
  expect(useApp.getState().data?.session?.id).toBe("current");
});
test("failed commands surface errors without inventing session state", async () => {
  vi.stubGlobal("window", {
    desktop: {
      command: vi.fn().mockRejectedValue(new Error("Service unavailable")),
    },
  });
  await expect(
    useApp.getState().command("new", { title: "User task" }),
  ).rejects.toThrow("Service unavailable");
  expect(useApp.getState().error).toBe("Service unavailable");
  expect(useApp.getState().data).toBeNull();
});
