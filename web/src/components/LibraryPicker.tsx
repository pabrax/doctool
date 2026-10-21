import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { api } from "@/lib/api";
import type { Doc } from "@/lib/types";
import { formatBytes } from "@/lib/utils";
import { Button } from "./Button";

interface Props {
  open: boolean;
  onClose: () => void;
  onPick: (doc: Doc) => void;
  /** Hide documents that cannot be used (e.g. encrypted ones). */
  filter?: (doc: Doc) => boolean;
}

/** Native <dialog>: focus trap, Esc to close and inert background come for free. */
export function LibraryPicker({ open, onClose, onPick, filter }: Props) {
  const { t } = useTranslation();
  const ref = useRef<HTMLDialogElement>(null);
  const { data = [], isLoading } = useQuery({ queryKey: ["documents"], queryFn: api.documents, enabled: open });

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    if (!open && el.open) el.close();
  }, [open]);

  const docs = filter ? data.filter(filter) : data;
  return (
    <dialog
      ref={ref}
      aria-labelledby="picker-title"
      onClose={onClose}
      className="m-auto w-[min(32rem,92vw)] rounded-xl border border-border bg-surface p-0 text-text"
    >
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 id="picker-title" className="text-base font-semibold">
          {t("toolPage.pickFromLibrary")}
        </h2>
        <Button variant="ghost" size="sm" onClick={onClose}>
          {t("common.close")}
        </Button>
      </div>
      <div className="max-h-[60vh] overflow-auto p-2">
        {isLoading && <p className="p-3 text-sm text-muted">{t("common.loading")}</p>}
        {!isLoading && docs.length === 0 && <p className="p-3 text-sm text-muted">{t("toolPage.libraryEmpty")}</p>}
        <ul>
          {docs.map((doc) => (
            <li key={doc.id}>
              <button
                type="button"
                className="flex w-full items-center gap-3 rounded-lg p-2 text-left hover:bg-surface-2"
                onClick={() => {
                  onPick(doc);
                  onClose();
                }}
              >
                <img
                  alt=""
                  loading="lazy"
                  src={api.thumbnailUrl(doc.latest_version.id, 1, 80)}
                  className="h-14 w-10 rounded border border-border bg-white object-cover"
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{doc.name}</span>
                  <span className="text-xs text-muted">
                    {doc.latest_version.pages ? t("common.pages", { count: doc.latest_version.pages }) : null}
                    {" · "}
                    {formatBytes(doc.latest_version.size)}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </dialog>
  );
}
