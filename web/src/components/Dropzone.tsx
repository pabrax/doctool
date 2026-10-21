import { Upload } from "lucide-react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { Tool } from "@/lib/types";
import { cn } from "@/lib/utils";

type Accepts = Tool["accepts"];

const isPdf = (f: File) => f.type === "application/pdf" || /\.pdf$/i.test(f.name);
const isImage = (f: File) => f.type.startsWith("image/") || /\.(jpe?g|png|webp|gif|bmp|tiff?)$/i.test(f.name);

export function acceptsFile(file: File, accepts: Accepts): boolean {
  if (accepts === "pdf") return isPdf(file);
  if (accepts === "image") return isImage(file);
  return isPdf(file) || isImage(file);
}

const acceptAttr: Record<Accepts, string> = {
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
}

export function Dropzone({ accepts, multiple = true, onFiles, extra, compact }: Props) {
  const { t } = useTranslation();
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [rejected, setRejected] = useState(0);

  const take = (list: FileList | null) => {
    if (!list) return;
    const all = Array.from(list);
    const ok = all.filter((f) => acceptsFile(f, accepts));
    setRejected(all.length - ok.length);
    if (ok.length) onFiles(multiple ? ok : ok.slice(0, 1));
  };
  const kind = accepts === "pdf" ? t("dropzone.pdf") : accepts === "image" ? t("dropzone.image") : t("dropzone.pdfImage");

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        take(e.dataTransfer.files);
      }}
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed text-center transition-colors",
        compact ? "px-4 py-6" : "px-6 py-12",
        over ? "border-accent bg-accent-soft" : "border-border bg-surface",
      )}
    >
      <Upload aria-hidden className="h-8 w-8 text-muted" />
      <p className="text-sm font-medium">{t("dropzone.title")}</p>
      <p className="text-xs text-muted">{kind}</p>
      <div className="flex flex-wrap items-center justify-center gap-2">
        <button
          type="button"
          className="inline-flex min-h-9 items-center rounded-md bg-accent px-3.5 py-2 text-sm font-medium text-accent-fg hover:brightness-110"
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
        accept={acceptAttr[accepts]}
        data-testid="file-input"
        onChange={(e) => {
          take(e.target.files);
          e.target.value = "";
        }}
      />
      {rejected > 0 && (
        <p role="alert" className="text-xs text-danger">
          {t("errors.damaged")} ({rejected})
        </p>
      )}
    </div>
  );
}
