const whole = new Intl.NumberFormat("en");
const share = new Intl.NumberFormat("en", { style: "percent", maximumFractionDigits: 0 });

/** 2497449 becomes "2,497,449". */
export function count(value: number): string {
  return whole.format(value);
}

export function percent(value: number | null | undefined): string {
  return value == null || !Number.isFinite(value) ? "n/a" : share.format(value);
}

export function fixed(value: number | null | undefined, digits = 2): string {
  return value == null || !Number.isFinite(value) ? "n/a" : value.toFixed(digits);
}

/** Round to a compact figure for headlines: 2497449 becomes "2.5 million". */
export function compact(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)} million`;
  return count(value);
}
