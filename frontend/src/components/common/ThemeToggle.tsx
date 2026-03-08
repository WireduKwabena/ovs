import React from "react";
import { Moon, Sun } from "lucide-react";

import { cn } from "@/lib/utils";
import { useTheme } from "@/hooks/useTheme";

type ThemeToggleProps = {
  className?: string;
  compact?: boolean;
};

export const ThemeToggle: React.FC<ThemeToggleProps> = ({ className, compact = false }) => {
  const { resolvedTheme, toggleTheme } = useTheme();
  const nextTheme = resolvedTheme === "dark" ? "light" : "dark";
  const label = `Switch to ${nextTheme} theme`;

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={label}
      title={label}
      className={cn(
        "inline-flex items-center justify-center rounded-md border border-border bg-card text-card-foreground transition hover:bg-accent hover:text-accent-foreground",
        compact ? "h-8 w-8" : "h-9 px-3 text-sm font-medium",
        className,
      )}
    >
      {resolvedTheme === "dark" ? (
        <Sun className={compact ? "h-4 w-4" : "mr-2 h-4 w-4"} />
      ) : (
        <Moon className={compact ? "h-4 w-4" : "mr-2 h-4 w-4"} />
      )}
      {compact ? null : <span className="leading-none">{resolvedTheme === "dark" ? "Light mode" : "Dark mode"}</span>}
    </button>
  );
};

export default ThemeToggle;
