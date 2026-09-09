import { forwardRef, type HTMLAttributes, type TableHTMLAttributes } from "react";
import { cn } from "../../lib/utils";
export const Table = forwardRef<HTMLTableElement, TableHTMLAttributes<HTMLTableElement>>(({ className, ...props }, ref) => <div className="w-full overflow-x-auto"><table ref={ref} className={cn("w-full text-left text-sm", className)} {...props} /></div>);
export const TableHead = ({ className, ...props }: HTMLAttributes<HTMLTableCellElement>) => <th className={cn("h-9 px-3 text-left text-xs font-medium text-slate-500", className)} {...props} />;
export const TableCell = ({ className, ...props }: HTMLAttributes<HTMLTableCellElement>) => <td className={cn("px-3 py-2.5 text-slate-700", className)} {...props} />;
