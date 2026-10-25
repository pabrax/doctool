/** Whole-number percentage saved (1..99), or null when the file did not get meaningfully smaller. */
export function savedPercent(before: number, after: number): number | null {
  if (before <= 0 || after >= before) return null;
  const pct = Math.min(99, Math.round((1 - after / before) * 100));
  return pct >= 1 ? pct : null;
}
