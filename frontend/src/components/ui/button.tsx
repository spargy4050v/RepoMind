import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "../../lib/utils";

const buttonVariants = cva("inline-flex items-center justify-center gap-2 rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50", { variants: { variant: { default: "bg-blue-700 text-white hover:bg-blue-800", outline: "border border-slate-300 bg-white text-slate-700 hover:bg-slate-100", ghost: "text-slate-600 hover:bg-slate-100 hover:text-slate-900", danger: "bg-red-700 text-white hover:bg-red-800" }, size: { default: "h-9 px-3", sm: "h-8 px-2.5 text-xs", lg: "h-10 px-4" } }, defaultVariants: { variant: "default", size: "default" } });
export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> { asChild?: boolean; }
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, asChild = false, ...props }, ref) => { const Comp = asChild ? Slot : "button"; return <Comp className={cn(buttonVariants({ variant, size }), className)} ref={ref} {...props} />; });
Button.displayName = "Button";
export { buttonVariants };
