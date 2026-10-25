import type { Tool } from "./types";

/** What people usually do with a result next. Order = priority; unknown tools get DEFAULT. */
const NEXT: Record<string, string[]> = {
  merge: ["organize", "compress", "pagenumber"],
  split: ["compress", "protect", "metadata"],
  rotate: ["organize", "compress", "merge"],
  compress: ["protect", "metadata", "merge"],
  imagepdf: ["merge", "compress", "organize"],
  metadata: ["compress", "protect"],
  watermark: ["compress", "protect", "pagenumber"],
  pagenumber: ["compress", "protect", "watermark"],
  unlock: ["organize", "compress", "merge"],
};
const DEFAULT = ["compress", "organize", "merge"];

/** Up to `limit` follow-up tools that exist, take a PDF and are not the tool just used. */
export function nextSteps(toolId: string, tools: Tool[], limit = 3): Tool[] {
  const byId = new Map(tools.map((x) => [x.id, x]));
  return (NEXT[toolId] ?? DEFAULT)
    .filter((id) => id !== toolId)
    .map((id) => byId.get(id))
    .filter((x): x is Tool => !!x && x.accepts !== "image")
    .slice(0, limit);
}
