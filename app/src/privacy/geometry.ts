import type { Cover, Rect, Segment } from "./types";
export function normalizeRect(rect: Rect): Rect {
  const x = Math.max(0, Math.min(1, rect.x)),
    y = Math.max(0, Math.min(1, rect.y));
  return {
    x,
    y,
    width: Math.max(0, Math.min(1 - x, rect.width)),
    height: Math.max(0, Math.min(1 - y, rect.height)),
  };
}
/** Half-open intervals prevent a cover bleeding into the next scene. */
export function rectAt(cover: Cover, time: number): Rect | null {
  if (time < cover.start || time >= cover.end || !cover.keyframes.length)
    return null;
  const frames = [...cover.keyframes].sort((a, b) => a.time - b.time);
  const right = frames.findIndex((f) => f.time > time);
  if (right === 0) return frames[0].rect;
  if (right < 0) return frames[frames.length - 1].rect;
  const a = frames[right - 1],
    b = frames[right],
    mix = (time - a.time) / (b.time - a.time);
  return normalizeRect({
    x: a.rect.x + (b.rect.x - a.rect.x) * mix,
    y: a.rect.y + (b.rect.y - a.rect.y) * mix,
    width: a.rect.width + (b.rect.width - a.rect.width) * mix,
    height: a.rect.height + (b.rect.height - a.rect.height) * mix,
  });
}
export function paintCovers(
  ctx: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D,
  covers: Cover[],
  segment: string,
  time: number,
  width: number,
  height: number,
  frameEnd = time,
) {
  ctx.fillStyle = "#111111";
  for (const cover of covers) {
    if (cover.segment !== segment) continue;
    // Cover the whole encoded frame when it overlaps the selected interval.
    // This may cover up to one extra frame, but never exposes a partial frame.
    const r = rectAt(
      cover,
      time < cover.start && frameEnd > cover.start ? cover.start : time,
    );
    // Expand by two source pixels to avoid interpolation/codec edge leakage.
    if (r)
      ctx.fillRect(
        Math.floor(r.x * width) - 2,
        Math.floor(r.y * height) - 2,
        Math.ceil(r.width * width) + 4,
        Math.ceil(r.height * height) + 4,
      );
  }
}
export function validateCovers(
  covers: Cover[],
  segments: Segment[],
  cuts: Record<string, number[]>,
) {
  for (const c of covers) {
    const segment = segments.find((s) => s.name === c.segment);
    if (!segment || c.end > segment.duration + 0.001)
      throw new Error("A cover extends beyond its recording segment.");
    if (
      !Number.isFinite(c.start) ||
      !Number.isFinite(c.end) ||
      c.start < 0 ||
      c.end <= c.start ||
      !c.keyframes.length
    )
      throw new Error("Every cover needs a valid start, end, and region.");
    if (
      (cuts[c.segment] || []).some(
        (cut) => cut > c.start + 0.001 && cut < c.end - 0.001,
      )
    )
      throw new Error(
        "A cover crosses a detected screen cut. Split it at the cut before approval.",
      );
    for (const f of c.keyframes) {
      if (
        ![f.time, ...Object.values(f.rect)].every(Number.isFinite) ||
        f.time < c.start ||
        f.time > c.end ||
        f.rect.width <= 0 ||
        f.rect.height <= 0 ||
        f.rect.x < 0 ||
        f.rect.y < 0 ||
        f.rect.x + f.rect.width > 1.001 ||
        f.rect.y + f.rect.height > 1.001
      )
        throw new Error("A cover contains an invalid position or keyframe.");
    }
  }
}
