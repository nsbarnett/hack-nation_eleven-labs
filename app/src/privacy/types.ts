/** Local-only edit decisions. No OCR text or original image bytes belong in API state. */
export type Rect = { x: number; y: number; width: number; height: number };
export type Keyframe = { time: number; rect: Rect };
export type Cover = {
  id: string;
  segment: string;
  start: number;
  end: number;
  keyframes: Keyframe[];
};
export type Marker = {
  id: string;
  segment: string;
  time: number;
  until?: number;
  category: string;
  rect?: Rect;
  decision: "pending" | "covered" | "dismissed";
};
export type Segment = {
  name: string;
  start: number;
  duration: number;
  width: number;
  height: number;
};
export type Review = {
  guest: string;
  session: string;
  revision: number;
  status: "draft" | "rendering" | "approved";
  segments: Segment[];
  covers: Cover[];
  markers: Marker[];
  cuts: Record<string, number[]>;
  scanned: number;
  expected: number;
  scan: "pending" | "scanning" | "complete" | "incomplete";
  gaps: string[];
  derivatives: Record<string, string>;
  uploaded: string[];
};
export const uid = () => crypto.randomUUID().replaceAll("-", "");
export function newReview(guest: string, session: string): Review {
  return {
    guest,
    session,
    revision: 0,
    status: "draft",
    segments: [],
    covers: [],
    markers: [],
    cuts: {},
    scanned: 0,
    expected: 0,
    scan: "pending",
    gaps: [],
    derivatives: {},
    uploaded: [],
  };
}
