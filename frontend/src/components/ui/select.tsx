import { forwardRef, type SelectHTMLAttributes } from "react";
import { cn } from "../../lib/utils";
export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(({ className, ...props }, ref) => <select ref={ref} className={cn("flex h-9 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100", className)} {...props} />);
Select.displayName = "Select";
