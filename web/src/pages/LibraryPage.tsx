import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Lock, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Button } from "@/components/Button";
import { Dropzone } from "@/components/Dropzone";
import { cardClass, inputClass } from "@/components/ui";
import { api } from "@/lib/api";
import { errorText } from "@/lib/errors";
import type { Doc } from "@/lib/types";
import { formatBytes, formatDate } from "@/lib/utils";

export function LibraryPage() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const [filter, setFilter] = useState("");
  const { data: docs, isLoading, error } = useQuery({ queryKey: ["documents"], queryFn: api.documents });

  const upload = useMutation({
    mutationFn: async (files: File[]) => {
      for (const f of files) await api.uploadDocument(f);
    },
    onSettled: () => void qc.invalidateQueries({ queryKey: ["documents"] }),
  });
  const remove = useMutation({
    mutationFn: (id: string) => api.deleteDocument(id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["documents"] }),
  });

  const visible = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q || !docs) return docs ?? [];
    return docs.filter((d) => d.name.toLowerCase().includes(q) || d.tags.some((tag) => tag.toLowerCase().includes(q)));
  }, [docs, filter]);

  return (
    <div className="mx-auto max-w-6xl p-4 sm:p-6">
      <h1 className="text-2xl font-semibold">{t("library.title")}</h1>
      <p className="mt-1 text-sm text-muted">{t("library.subtitle")}</p>

      <div className="mt-6">
        <Dropzone accepts="pdf" compact onFiles={(files) => upload.mutate(files)} />
        <div aria-live="polite" className="mt-2 text-sm">
          {upload.isPending && <p className="text-muted">{t("library.uploading")}</p>}
          {upload.isError && (
            <p role="alert" className="text-danger">
              {errorText(t, upload.error)}
            </p>
          )}
        </div>
      </div>

      {docs && docs.length > 0 && (
        <div className="mt-4 max-w-sm">
          <label className="sr-only" htmlFor="lib-filter">
            {t("library.search")}
          </label>
          <input
            id="lib-filter"
            type="search"
            className={inputClass}
            placeholder={t("library.search")}
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>
      )}

      {isLoading && <p className="mt-6 text-sm text-muted">{t("common.loading")}</p>}
      {error && (
        <p role="alert" className="mt-6 text-sm text-danger">
          {errorText(t, error)}
        </p>
      )}
      {docs && docs.length === 0 && <p className="mt-6 text-sm text-muted">{t("library.empty")}</p>}
      {docs && docs.length > 0 && visible.length === 0 && <p className="mt-6 text-sm text-muted">{t("library.noResults")}</p>}

      <ul className="mt-6 grid grid-cols-[repeat(auto-fill,minmax(11rem,1fr))] gap-4">
        {visible.map((doc) => (
          <DocCard
            key={doc.id}
            doc={doc}
            locale={i18n.language}
            onDelete={() => {
              if (window.confirm(t("library.confirmDelete", { name: doc.name }))) remove.mutate(doc.id);
            }}
          />
        ))}
      </ul>
    </div>
  );
}

function DocCard({ doc, locale, onDelete }: { doc: Doc; locale: string; onDelete: () => void }) {
  const { t } = useTranslation();
  const v = doc.latest_version;
  return (
    <li className={`${cardClass} flex flex-col overflow-hidden`}>
      <Link to={`/library/${doc.id}`} className="block bg-surface-2" aria-label={`${t("common.open")}: ${doc.name}`}>
        {v.encrypted ? (
          <div className="flex aspect-[3/4] items-center justify-center text-muted">
            <Lock aria-hidden className="h-10 w-10" />
          </div>
        ) : (
          <img
            alt=""
            loading="lazy"
            src={api.thumbnailUrl(v.id, 1, 320)}
            className="aspect-[3/4] w-full bg-white object-cover object-top"
          />
        )}
      </Link>
      <div className="flex flex-1 flex-col gap-1 p-3">
        <Link to={`/library/${doc.id}`} className="truncate text-sm font-medium hover:underline" title={doc.name}>
          {doc.name}
        </Link>
        <p className="text-xs text-muted">
          {v.encrypted ? t("common.encrypted") : v.pages ? t("common.pages", { count: v.pages }) : ""}
          {" · "}
          {formatBytes(v.size)}
        </p>
        <p className="text-xs text-muted">
          {t("common.version", { n: v.seq })} · {formatDate(v.created_at, locale)}
        </p>
        {doc.tags.length > 0 && (
          <p className="mt-1 flex flex-wrap gap-1">
            {doc.tags.map((tag) => (
              <span key={tag} className="rounded-full bg-accent-soft px-2 py-0.5 text-xs text-accent">
                {tag}
              </span>
            ))}
          </p>
        )}
        <div className="mt-auto flex gap-1 pt-2">
          <a
            href={api.versionDownloadUrl(v.id)}
            aria-label={`${t("common.download")}: ${doc.name}`}
            className="inline-flex h-8 w-8 items-center justify-center rounded-md hover:bg-surface-2"
          >
            <Download aria-hidden className="h-4 w-4" />
          </a>
          <Button variant="ghost" size="icon" className="h-8 w-8" aria-label={`${t("common.delete")}: ${doc.name}`} onClick={onDelete}>
            <Trash2 aria-hidden className="h-4 w-4 text-danger" />
          </Button>
        </div>
      </div>
    </li>
  );
}
