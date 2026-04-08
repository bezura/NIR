import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "../../lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full text-sm font-medium transition duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/55 disabled:pointer-events-none disabled:opacity-40",
  {
    variants: {
      variant: {
        primary:
          "bg-foreground px-5 py-3 text-background shadow-[0_0_0_1px_rgba(255,255,255,0.12)] hover:scale-[1.01] hover:opacity-95",
        ghost:
          "bg-transparent px-4 py-2.5 text-foreground/84 hover:bg-white/[0.05] hover:text-foreground",
        panel:
          "bg-white/[0.04] px-4 py-2.5 text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] hover:bg-white/[0.08]",
        subtle:
          "bg-white/[0.03] px-3 py-2 text-muted-foreground hover:bg-white/[0.06] hover:text-foreground",
      },
      size: {
        default: "",
        sm: "h-9 px-3 text-xs",
        lg: "px-6 py-3.5 text-base",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button className={cn(buttonVariants({ variant, size }), className)} ref={ref} {...props} />
  ),
);
Button.displayName = "Button";

export { Button, buttonVariants };
