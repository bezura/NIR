import * as React from "react";

import { cn } from "../../lib/utils";

const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      className={cn(
        "flex h-12 w-full rounded-2xl border border-white/10 bg-white/[0.035] px-4 py-3 text-sm text-foreground outline-none transition duration-200 placeholder:text-muted-foreground focus:border-white/20 focus:bg-white/[0.05] focus:ring-2 focus:ring-accent/35",
        className,
      )}
      ref={ref}
      {...props}
    />
  ),
);

Input.displayName = "Input";

export { Input };
