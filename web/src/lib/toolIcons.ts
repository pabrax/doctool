import {
  ArrowRightLeft,
  CodeXml,
  Combine,
  Crop,
  FileText,
  Hash,
  ImageDown,
  Images,
  FileImage,
  FileChartColumn,
  FilePenLine,
  FileSpreadsheet,
  FileType,
  LayoutGrid,
  Lock,
  LockOpen,
  Presentation,
  Minimize2,
  RotateCw,
  Scaling,
  Scissors,
  ShieldCheck,
  Stamp,
  Table2,
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
  imageconvert: ArrowRightLeft,
  imagecompress: ImageDown,
  imageresize: Scaling,
  imagecrop: Crop,
  imageclean: ShieldCheck,
  word2pdf: FileType,
  excel2pdf: FileSpreadsheet,
  ppt2pdf: Presentation,
  html2pdf: CodeXml,
  pdf2word: FilePenLine,
  pdf2excel: Table2,
  pdf2ppt: FileChartColumn,
};

export const GROUPS = ["organize", "optimize", "convert", "office", "edit", "security", "images"] as const;
export type Group = (typeof GROUPS)[number];

export const isKnownGroup = (g: string): g is Group => (GROUPS as readonly string[]).includes(g);
export const hasToolIcon = (id: string) => id in TOOL_ICONS;
export const toolIcon = (id: string): LucideIcon => TOOL_ICONS[id] ?? FileText;
