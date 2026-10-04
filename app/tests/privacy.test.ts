import { expect, test } from "vitest";
import { detectLines } from "../src/privacy/detect";
import { rectAt, validateCovers } from "../src/privacy/geometry";
import { validAction, validSnapshot, offline } from "../extension/protocol";
const rect = { x: 0.1, y: 0.2, width: 0.2, height: 0.1 };
const cover = {
  id: "mask",
  segment: "clip",
  start: 1,
  end: 3,
  keyframes: [
    { time: 1, rect },
    { time: 2, rect: { ...rect, x: 0.5 } },
  ],
};
test("solid covers follow keyframes only inside their interval and segment", () => {
  expect(rectAt(cover, 0.999)).toBeNull();
  expect(rectAt(cover, 3)).toBeNull();
  expect(rectAt(cover, 1.5)?.x).toBeCloseTo(0.3);
  const segment = {
    name: "clip",
    start: 0,
    duration: 5,
    width: 100,
    height: 100,
  };
  expect(() => validateCovers([cover], [segment], { clip: [2] })).toThrow(
    /cut/,
  );
  expect(() => validateCovers([cover], [segment], {})).not.toThrow();
  expect(() => validateCovers([{ ...cover, end: 6 }], [segment], {})).toThrow(
    /beyond/,
  );
});
test("detector flags common patterns but returns no recognized text", () => {
  const text =
    "test@example.test +1 212-555-0199 4111 1111 1111 1111 api_key: sk-testfixture12345";
  const result = detectLines(
    [{ text, bbox: { x0: 10, y0: 20, x1: 400, y1: 50 } }],
    640,
    360,
  );
  expect(result.map((r) => r.category)).toEqual(
    expect.arrayContaining([
      "Possible email",
      "Possible phone number",
      "Possible payment card",
      "Possible credential",
    ]),
  );
  expect(JSON.stringify(result)).not.toContain("example.test");
  expect(
    detectLines(
      [
        {
          text: "4111 1111 1111 1112",
          bbox: { x0: 0, y0: 0, x1: 100, y1: 20 },
        },
      ],
      640,
      360,
    ),
  ).toEqual([]);
});
test("extension protocol accepts only typed commands and bounded snapshots", () => {
  expect(validSnapshot(offline)).toBe(true);
  expect(validSnapshot({ ...offline, question: { id: "q", text: 15 } })).toBe(
    false,
  );
  const command = {
    type: "command",
    id: "1234567890123456",
    action: "context",
    text: "User note",
    epoch: "epoch",
    session: "s",
    question: null,
  };
  expect(validAction(command)).toBe(true);
  expect(validAction({ ...command, action: "execute" })).toBe(false);
  expect(validAction({ ...command, text: "x".repeat(12001) })).toBe(false);
});
