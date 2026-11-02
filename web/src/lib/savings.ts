/** Whole-number percentage a file grew (1 or more), or null when it did not get meaningfully bigger. */
export function grownPercent(before: number, after: number): number | null {
  if (before <= 0 || after <= before) return null;
  const pct = Math.round((after / before - 1) * 100);
  return pct >= 1 ? pct : null;
}

/** Whole-number percentage saved (1..99), or null when the file did not get meaningfully smaller. */
export function savedPercent(before: number, after: number): number | null {
  if (before <= 0 || after >= before) return null;
  const pct = Math.min(99, Math.round((1 - after / before) * 100));
  return pct >= 1 ? pct : null;
}
