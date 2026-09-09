import * as TabsPrimitive from "@radix-ui/react-tabs";
import { forwardRef, type ComponentPropsWithoutRef, type ElementRef } from "react";
import { cn } from "../../lib/utils";
export const Tabs = TabsPrimitive.Root;
export const TabsList = forwardRef<ElementRef<typeof TabsPrimitive.List>, ComponentPropsWithoutRef<typeof TabsPrimitive.List>>(({ className, ...props }, ref) => <TabsPrimitive.List ref={ref} className={cn("inline-flex h-9 items-center rounded-md bg-slate-100 p-1", className)} {...props} />);
export const TabsTrigger = forwardRef<ElementRef<typeof TabsPrimitive.Trigger>, ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>>(({ className, ...props }, ref) => <TabsPrimitive.Trigger ref={ref} className={cn("rounded px-3 py-1 text-sm text-slate-600 data-[state=active]:bg-white data-[state=active]:font-medium data-[state=active]:text-slate-900 data-[state=active]:shadow-sm", className)} {...props} />);
export const TabsContent = TabsPrimitive.Content;
