export function round2(value) {
  return Math.round(Number(value) * 100) / 100;
}

export function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

export function asNumber(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}
