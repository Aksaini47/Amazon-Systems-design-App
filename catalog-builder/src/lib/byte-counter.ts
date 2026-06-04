const encoder = new TextEncoder();

export function byteLength(s: string): number {
  return encoder.encode(s).byteLength;
}

export function charLength(s: string): number {
  return [...s].length;
}

export type LimitTier = "ok" | "warn" | "error";

export interface LimitState {
  used: number;
  limit: number;
  warnAt: number;
  tier: LimitTier;
  remaining: number;
  percent: number;
}

export function evaluateLimit(used: number, limit: number, warnAt: number): LimitState {
  let tier: LimitTier = "ok";
  if (used > limit) tier = "error";
  else if (used > warnAt) tier = "warn";
  return {
    used,
    limit,
    warnAt,
    tier,
    remaining: limit - used,
    percent: Math.min(100, Math.round((used / limit) * 100)),
  };
}
