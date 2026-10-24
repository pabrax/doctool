import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

export const GROUP_ORDER = ["organize", "optimize", "convert", "edit", "security"] as const;

/** Tools ordered by group (GROUP_ORDER), keeping registry order inside a group; unknown groups last. */
export function sortByGroup<T extends { group: string }>(tools: T[]): T[] {
  const rank = (g: string) => {
    const i = (GROUP_ORDER as readonly string[]).indexOf(g);
    return i < 0 ? GROUP_ORDER.length : i;
  };
  return tools
    .map((t, i) => [t, i] as const)
    .sort((a, b) => rank(a[0].group) - rank(b[0].group) || a[1] - b[1])
    .map(([t]) => t);
}

export function useTools() {
  return useQuery({ queryKey: ["tools"], queryFn: api.tools, staleTime: Infinity });
}

/** The organizer has a dedicated visual page; every other tool uses the generic one. */
export const toolPath = (toolId: string, versionId?: string) =>
  toolId === "organize" ? `/organize${versionId ? `/${versionId}` : ""}` : `/tools/${toolId}`;
