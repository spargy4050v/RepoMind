import { cva, type VariantProps } from "class-variance-authority";
import { type HTMLAttributes } from "react";
import { cn } from "../../lib/utils";
const badgeVariants = cva("inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium", { variants: { variant: { neutral: "border-slate-200 bg-slate-100 text-slate-700", info: "border-blue-200 bg-blue-50 text-blue-800", low: "border-emerald-200 bg-emerald-50 text-emerald-800", medium: "border-amber-200 bg-amber-50 text-amber-900", high: "border-red-200 bg-red-50 text-red-800" } }, defaultVariants: { variant: "neutral" } });
export function Badge({ className, variant, ...props }: HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) { return <span className={cn(badgeVariants({ variant }), className)} {...props} />; }
