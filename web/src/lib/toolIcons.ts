import {
  Combine,
  FileText,
  Hash,
  Images,
  FileImage,
  LayoutGrid,
  Lock,
  LockOpen,
  Minimize2,
  RotateCw,
  Scissors,
  Stamp,
  Tag,
  type LucideIcon,
} from "lucide-react";

/** One Lucide icon per registered tool id. Unknown (future) tools fall back to a generic document. */
export const TOOL_ICONS: Record<string, LucideIcon> = {
  merge: Combine,
  split: Scissors,
  rotate: RotateCw,
  organize: LayoutGrid,
  compress: Minimize2,
  imagepdf: Images,
  pdfimage: FileImage,
  metadata: Tag,
  watermark: Stamp,
  pagenumber: Hash,
  protect: Lock,
  unlock: LockOpen,
};

export const GROUPS = ["organize", "optimize", "convert", "edit", "security"] as const;
export type Group = (typeof GROUPS)[number];

export const isKnownGroup = (g: string): g is Group => (GROUPS as readonly string[]).includes(g);
export const hasToolIcon = (id: string) => id in TOOL_ICONS;
export const toolIcon = (id: string): LucideIcon => TOOL_ICONS[id] ?? FileText;
