import * as React from "react";

import { cn } from "../../lib/utils";

interface SwitchProps {
  checked: boolean;
  onCheckedChange(checked: boolean): void;
  className?: string;
}

function Switch({ checked, onCheckedChange, className }: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        "peer inline-flex h-7 w-12 shrink-0 cursor-pointer items-center rounded-full border border-white/12 transition-colors",
        checked ? "border-accent/70 bg-accent/70" : "bg-white/[0.05]",
        className,
      )}
    >
      <span
        className={cn(
          "block h-5 w-5 rounded-full bg-white shadow-lg transition-transform",
          checked ? "translate-x-[22px]" : "translate-x-1",
        )}
      />
    </button>
  );
}

export { Switch };
