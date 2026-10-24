import { cn } from "@/lib/utils";
import { hasToolIcon, isKnownGroup, toolIcon } from "@/lib/toolIcons";

interface Props {
  toolId: string;
  group: string;
  /** "tile" is a tinted square; "bare" is just the glyph in the group ink color. */
  variant?: "tile" | "bare";
  className?: string;
}

/** Tool glyph colored by its group. Decorative: the tool name is always next to it as text. */
export function ToolIcon({ toolId, group, variant = "tile", className }: Props) {
  const Icon = toolIcon(toolId);
  return (
    <span
      data-group={isKnownGroup(group) ? group : "none"}
      data-tool-icon={hasToolIcon(toolId) ? toolId : "fallback"}
      className={cn(
        "inline-flex shrink-0 items-center justify-center text-g-ink",
        variant === "tile" ? "h-9 w-9 rounded-lg bg-g-soft" : "h-5 w-5",
        className,
      )}
    >
      <Icon aria-hidden className={variant === "tile" ? "h-[1.15rem] w-[1.15rem]" : "h-4 w-4"} strokeWidth={2} />
    </span>
  );
}
