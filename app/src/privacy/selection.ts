import type { Segment } from "./types";

export type Sample = { time: number; change: number };
export type FrameSelection = { segment: Segment; time: number };

/** A bounded, local heuristic. A change is useful only if the vision observer
 * subsequently establishes a readable event; pixel differences prove no intent. */
export function selectAnalysisFrames(groups: { segment: Segment; samples: Sample[] }[]): FrameSelection[] {
  const budget = Math.min(30, groups.reduce((n, g) => n + Math.max(1, Math.ceil(g.segment.duration / 10)), 0));
  const all = groups.flatMap(({ segment, samples }) => samples.map((s) => ({ segment, time: s.time })))
    .sort((a, b) => a.segment.start + a.time - b.segment.start - b.time);
  if (!all.length) return [];
  const selected = new Map<string, FrameSelection>();
  const key = (f: FrameSelection) => `${f.segment.name}:${f.time}`;
  const add = (f: FrameSelection) => selected.set(key(f), f);
  add(all[0]);
  if (budget > 1) add(all[all.length - 1]);
  const changes = groups.flatMap(({ segment, samples }) => samples.flatMap((s, i) =>
    i > 0 && s.change >= 0.06 && (i === samples.length - 1 || samples[i + 1].change <= 0.02)
      ? [{ score: s.change, pair: [samples[i - 1], s].map((f) => ({ segment, time: f.time })) }] : []));
  changes.sort((a, b) => b.score - a.score);
  for (const change of changes) {
    const fresh = change.pair.filter((f) => !selected.has(key(f)));
    if (selected.size + fresh.length <= budget) fresh.forEach(add);
  }
  // Fill remaining capacity evenly through time. Never truncate an accepted pair.
  for (let i = 1; selected.size < budget && i < budget; i++) add(all[Math.round(i * (all.length - 1) / budget)]);
  return [...selected.values()].sort((a, b) => a.segment.start + a.time - b.segment.start - b.time);
}

/** Maximum mean RGB difference in a 16px tile keeps small field edits visible. */
export function frameDifference(a: Uint8ClampedArray, b: Uint8ClampedArray, width: number, height: number) {
  let max = 0;
  for (let y = 0; y < height; y += 16) for (let x = 0; x < width; x += 16) {
    let sum = 0, count = 0;
    for (let yy = y; yy < Math.min(height, y + 16); yy++) for (let xx = x; xx < Math.min(width, x + 16); xx++) {
      const p = (yy * width + xx) * 4;
      sum += Math.abs(a[p] - b[p]) + Math.abs(a[p + 1] - b[p + 1]) + Math.abs(a[p + 2] - b[p + 2]);
      count += 3;
    }
    max = Math.max(max, sum / (count * 255));
  }
  return max;
}
