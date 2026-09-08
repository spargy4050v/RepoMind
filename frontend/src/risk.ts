export type RiskTier = "green" | "amber" | "red";

export const RISK_TIERS: Record<RiskTier, { label: string; badgeClass: string }> = {
  green: { label: "Low", badgeClass: "bg-emerald-400/15 text-emerald-200 ring-emerald-400/30" },
  amber: { label: "Review", badgeClass: "bg-amber-400/15 text-amber-100 ring-amber-400/30" },
  red: { label: "High", badgeClass: "bg-rose-400/15 text-rose-100 ring-rose-400/30" },
};

/** Return the shared review tier: green <40, amber 40-70, red >70. */
export function riskTier(score: number): RiskTier {
  if (score > 70) return "red";
  if (score >= 40) return "amber";
  return "green";
}
