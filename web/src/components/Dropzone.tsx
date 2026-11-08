import { FileUp, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { Tool } from "@/lib/types";
import { cn } from "@/lib/utils";

type Accepts = Tool["accepts"];

const isPdf = (f: File) => f.type === "application/pdf" || /\.pdf$/i.test(f.name);
const isImage = (f: File) => f.type.startsWith("image/") || /\.(jpe?g|png|webp|gif|bmp|tiff?)$/i.test(f.name);

// Macro-enabled Office files are never accepted, whatever a tool lists (the server refuses them too).
const MACRO_FILE = /\.(docm|xlsm|pptm|dotm|xltm|potm|ppsm|xlam)$/i;
const extOf = (f: File) => f.name.toLowerCase().split(".").slice(1).pop() ?? "";

export function acceptsFile(file: File, accepts: Accepts, extensions: string[] = []): boolean {
  if (accepts === "office") return !MACRO_FILE.test(file.name) && extensions.includes(extOf(file));
  if (accepts === "pdf") return isPdf(file);
  if (accepts === "image") return isImage(file);
  return isPdf(file) || isImage(file);
}

const acceptAttr: Record<Exclude<Accepts, "office">, string> = {
  pdf: ".pdf,application/pdf",
  image: "image/*",
  "pdf+image": ".pdf,application/pdf,image/*",
};

interface Props {
  accepts: Accepts;
  multiple?: boolean;
  onFiles: (files: File[]) => void;
  /** Extra controls rendered next to the select button (e.g. "From library"). */
  extra?: React.ReactNode;
  compact?: boolean;
  /** Tool group; the images group names only the still formats it handles. */
  group?: string;
  /** File extensions an `office` tool takes (lower-case, no dot). */
  extensions?: string[];
  /** Engine missing: the zone neither opens the picker nor takes drops. */
  disabled?: boolean;
}

export function Dropzone({ accepts, multiple = true, onFiles, extra, compact, group, extensions = [], disabled }: Props) {
  const { t } = useTranslation();
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [rejectedFiles, setRejectedFiles] = useState<string[]>([]);
  const rejected = rejectedFiles.length;

  const take = (list: FileList | null) => {
    if (!list || disabled) return;
    const all = Array.from(list);
    const ok = all.filter((f) => acceptsFile(f, accepts, extensions));
    setRejectedFiles(all.filter((f) => !ok.includes(f)).map((f) => f.name));
    if (ok.length) onFiles(multiple ? ok : ok.slice(0, 1));
  };
  const kind =
    accepts === "office"
      ? t("dropzone.office", { list: extensions.map((e) => e.toUpperCase()).join(", ") })
      : accepts === "pdf"
      ? t("dropzone.pdf")
      : accepts === "image"
        ? group === "images"
          ? t("dropzone.imageStill")
          : t("dropzone.image")
        : t("dropzone.pdfImage");

  /** Name the refused files and say what to do; office and PDF tools are specific. */
  const rejectionText = () => {
    const names = rejectedFiles.join(", ");
    const opts = { names, interpolation: { escapeValue: false } };
    if (accepts === "office") {
      if (rejectedFiles.some((n) => MACRO_FILE.test(n))) return t("dropzone.rejectedMacro", opts);
      return t("dropzone.rejectedOffice", { ...opts, list: extensions.map((e) => e.toUpperCase()).join(", ") });
    }
    if (accepts === "pdf") return t("dropzone.rejectedPdf", opts);
    if (accepts === "image") return `${t("dropzone.rejectedImage")} (${rejected})`;
    return `${t("errors.damaged")} (${rejected})`;
  };

  return (
    <div
      aria-disabled={disabled || undefined}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        take(e.dataTransfer.files);
      }}
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed text-center transition duration-200 motion-reduce:transform-none",
        compact ? "px-4 py-3 sm:flex-row sm:justify-center sm:gap-4" : "px-6 py-14",
        over ? "scale-[1.01] border-g bg-g-soft shadow-card" : "border-border bg-surface",
      )}
    >
      <span
        aria-hidden
        className={cn(
          "inline-flex items-center justify-center rounded-2xl bg-g-soft text-g-ink transition duration-200",
          compact ? "h-10 w-10" : "h-14 w-14",
          over && "-translate-y-1 scale-110 bg-g text-g-fg",
        )}
      >
        {over ? <FileUp className="h-6 w-6" /> : <Upload className="h-6 w-6" />}
      </span>
      <p className={cn("font-display font-semibold", compact ? "text-base" : "text-xl")}>
        {over ? t("dropzone.release") : t("dropzone.title")}
      </p>
      <p className="text-xs text-muted">{kind}</p>
      <div className="flex flex-wrap items-center justify-center gap-2">
        <button
          type="button"
          className="inline-flex min-h-10 items-center rounded-lg bg-g px-4 py-2 text-sm font-medium text-g-fg shadow-sm transition hover:brightness-95 active:translate-y-px"
          disabled={disabled}
          onClick={() => input.current?.click()}
        >
          {t("dropzone.pick")}
        </button>
        {extra}
      </div>
      <input
        ref={input}
        type="file"
        hidden
        multiple={multiple}
        accept={accepts === "office" ? extensions.map((e) => `.${e}`).join(",") : acceptAttr[accepts]}
        data-testid="file-input"
        onChange={(e) => {
          take(e.target.files);
          e.target.value = "";
        }}
      />
      {rejected > 0 && (
        <p role="alert" className="text-xs text-danger">
          {rejectionText()}
        </p>
      )}
    </div>
  );
}
