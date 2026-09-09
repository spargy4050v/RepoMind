export type RiskTier = "green" | "amber" | "red";

export const RISK_TIERS: Record<RiskTier, { label: string; badgeClass: string; variant: "low" | "medium" | "high" }> = {
  green: { label: "Low", badgeClass: "border-emerald-200 bg-emerald-50 text-emerald-800", variant: "low" },
  amber: { label: "Review", badgeClass: "border-amber-200 bg-amber-50 text-amber-900", variant: "medium" },
  red: { label: "High", badgeClass: "border-red-200 bg-red-50 text-red-800", variant: "high" },
};

/** Return the shared review tier: green <40, amber 40-70, red >70. */
export function riskTier(score: number): RiskTier {
  if (score > 70) return "red";
  if (score >= 40) return "amber";
  return "green";
}
