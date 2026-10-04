import type { Rect } from "./types";
export type TextLine = {
  text: string;
  bbox: { x0: number; y0: number; x1: number; y1: number };
};
function luhn(text: string) {
  const digits = text.replace(/\D/g, "");
  if (digits.length < 13 || digits.length > 19 || /^(\d)\1+$/.test(digits))
    return false;
  return (
    [...digits].reverse().reduce((sum, c, i) => {
      let n = Number(c);
      if (i % 2) {
        n *= 2;
        if (n > 9) n -= 9;
      }
      return sum + n;
    }, 0) %
      10 ===
    0
  );
}
/** Heuristics over local OCR. Values are discarded; markers contain only category + bounds. */
export function detectLines(
  lines: TextLine[],
  width: number,
  height: number,
): { category: string; rect: Rect }[] {
  const found: { category: string; rect: Rect }[] = [];
  for (const [index, line] of lines.entries()) {
    const t = line.text;
    const categories: string[] = [];
    if (/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i.test(t))
      categories.push("Possible email");
    if (/(?:\+\d{1,3}[ .-]?)?(?:\(\d{3}\)|\d{3})[ .-]\d{3}[ .-]\d{4}\b/.test(t))
      categories.push("Possible phone number");
    if (
      [...t.matchAll(/(?=(\b(?:\d[ -]?){13,19}\b))/g)].some((m) => luhn(m[1]))
    )
      categories.push("Possible payment card");
    if (
      /\b(?:sk-[a-z0-9_-]{12,}|gh[pousr]_[a-z0-9]{12,}|AKIA[A-Z0-9]{16})\b/i.test(
        t,
      ) ||
      /(?:api[ _-]?key|password|secret|access[ _-]?token)\s*[:=]\s*\S{4,}/i.test(
        t,
      )
    )
      categories.push("Possible credential");
    const nearby = lines[index - 1];
    const accountLabel =
      /(?:account|routing|iban|social security|ssn)\s*(?:number|no\.?|#)?/i;
    if (
      (accountLabel.test(t) && /\d[\d A-Z-]{4,}/i.test(t)) ||
      (nearby &&
        accountLabel.test(nearby.text) &&
        line.bbox.y0 - nearby.bbox.y1 < 60 &&
        /\d[\d A-Z-]{4,}/i.test(t))
    )
      categories.push("Possible account identifier");
    const b = line.bbox;
    for (const category of categories)
      found.push({
        category,
        rect: {
          x: Math.max(0, b.x0 - 6) / width,
          y: Math.max(0, b.y0 - 4) / height,
          width:
            Math.min(width - Math.max(0, b.x0 - 6), b.x1 - b.x0 + 12) / width,
          height:
            Math.min(height - Math.max(0, b.y0 - 4), b.y1 - b.y0 + 8) / height,
        },
      });
  }
  return found;
}
