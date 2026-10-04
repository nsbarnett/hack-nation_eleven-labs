import { create } from "zustand";
import type { State, MediaStatus } from "./types";
export type Page =
  | "Home"
  | "Record"
  | "Workflows"
  | "Work Map"
  | "Debrief"
  | "Teach"
  | "Privacy Review"
  | "Library"
  | "Settings";
type Store = {
  data: State | null;
  page: Page;
  error: string;
  notice: string;
  focusContext: boolean;
  refresh: () => Promise<void>;
  go: (page: Page) => void;
  command: (name: string, data?: unknown) => Promise<any>;
  fail: (error: unknown) => void;
};
export const useApp = create<Store>((set, get) => ({
  data: null,
  page: "Home",
  error: "",
  notice: "",
  focusContext: false,
  refresh: async () => {
    try {
      const data = await window.desktop.state();
      if (!get().data || data.epoch !== get().data!.epoch || data.sequence >= get().data!.sequence) set({ data });
    } catch (error) {
      get().fail(error);
    }
  },
  go: (page) => set({ page }),
  command: async (name, data = {}) => {
    try {
      const result = await window.desktop.command(name, data);
      await get().refresh();
      return result;
    } catch (error) {
      get().fail(error);
      throw error;
    }
  },
  fail: (error) =>
    set({ error: error instanceof Error ? error.message : String(error) }),
}));
export const useMedia = create<{
  status: MediaStatus;
  stream: MediaStream | null;
  sourceName: string;
  safePreview: boolean;
}>(() => ({
  status: { state: "idle", muted: true, voice: "idle", duration: 0 },
  stream: null,
  sourceName: "",
  safePreview: false,
}));
export function report(error: unknown) {
  useApp.getState().fail(error);
}
export function run(work: () => Promise<unknown>) {
  void work().catch(report);
}
