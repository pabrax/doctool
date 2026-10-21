import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

export const GROUP_ORDER = ["organize", "optimize", "convert", "edit", "security"] as const;

export function useTools() {
  return useQuery({ queryKey: ["tools"], queryFn: api.tools, staleTime: Infinity });
}

/** The organizer has a dedicated visual page; every other tool uses the generic one. */
export const toolPath = (toolId: string, versionId?: string) =>
  toolId === "organize" ? `/organize${versionId ? `/${versionId}` : ""}` : `/tools/${toolId}`;
