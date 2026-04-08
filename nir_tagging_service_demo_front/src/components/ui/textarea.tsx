import * as React from "react";

import { cn } from "../../lib/utils";

const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea
      className={cn(
        "flex min-h-[140px] w-full rounded-[26px] border border-white/10 bg-white/[0.035] px-4 py-3 text-sm text-foreground outline-none transition duration-200 placeholder:text-muted-foreground focus:border-white/20 focus:bg-white/[0.05] focus:ring-2 focus:ring-accent/35",
        className,
      )}
      ref={ref}
      {...props}
    />
  ),
);

Textarea.displayName = "Textarea";

export { Textarea };
