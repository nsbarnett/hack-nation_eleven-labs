import { expect, test } from "vitest";
import { frameDifference, selectAnalysisFrames } from "../src/privacy/selection";
const segment = { name: "reviewed.webm", start: 0, duration: 40, width: 320, height: 180 };

test("approved-frame selection preserves a brief stable change and both boundaries within budget", () => {
  const samples = Array.from({ length: 40 }, (_, i) => ({ time: i, change: i === 7 ? .4 : 0 }));
  const frames = selectAnalysisFrames([{ segment, samples }]);
  expect(frames.map((f) => f.time)).toEqual([0, 6, 7, 39]);
  expect(frames).toHaveLength(4);
});
test("many changes never exceed 30 uploads and pairs remain chronological", () => {
  const samples = Array.from({ length: 300 }, (_, i) => ({ time: i, change: i % 3 === 0 ? .4 : 0 }));
  const frames = selectAnalysisFrames([{ segment: { ...segment, duration: 300 }, samples }]);
  expect(frames.length).toBeLessThanOrEqual(30);
  expect(frames[0].time).toBe(0);
  expect(frames.at(-1)?.time).toBe(299);
  expect(new Set(frames.map((f) => f.time)).size).toBe(frames.length);
});
test("a short recording keeps its original one-frame budget", () => {
  const frames = selectAnalysisFrames([{ segment: { ...segment, duration: 4 }, samples: [{ time: 0, change: 0 }, { time: 3.99, change: .4 }] }]);
  expect(frames).toHaveLength(1);
});
test("small field edits remain candidates while identical pixels have zero change", () => {
  const a = new Uint8ClampedArray(64 * 64 * 4), b = a.slice();
  for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) {
    const i = (y * 64 + x) * 4; b[i] = 255; b[i+1] = 255; b[i+2] = 255;
  }
  expect(frameDifference(a, a, 64, 64)).toBe(0);
  expect(frameDifference(a, b, 64, 64)).toBe(1);
});
