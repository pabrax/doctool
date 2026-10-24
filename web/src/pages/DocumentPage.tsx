import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/Button";
import { cardClass, inputClass, labelClass, hintClass } from "@/components/ui";
import { ToolIcon } from "@/components/ToolIcon";
import { api } from "@/lib/api";
import { isKnownGroup } from "@/lib/toolIcons";
import { errorText } from "@/lib/errors";
import type { InputRef, Version } from "@/lib/types";
import { sortByGroup, toolPath, useTools } from "@/lib/useTools";
import { formatBytes, formatDate, uid } from "@/lib/utils";

export function DocumentPage() {
  const { docId = "" } = useParams();
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: tools } = useTools();
  const doc = useQuery({ queryKey: ["document", docId], queryFn: () => api.document(docId) });
  const versions = useQuery({ queryKey: ["versions", docId], queryFn: () => api.versions(docId) });
  const [selected, setSelected] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [tags, setTags] = useState("");

  useEffect(() => {
    if (doc.data) {
      setName(doc.data.name);
      setTags(doc.data.tags.join(", "));
    }
  }, [doc.data]);

  const current: Version | undefined =
    versions.data?.find((v) => v.id === selected) ?? versions.data?.at(-1) ?? doc.data?.latest_version;
  const meta = useQuery({
    queryKey: ["metadata", current?.id],
    queryFn: () => api.metadata(current!.id),
    enabled: !!current && !current.encrypted,
  });

  const save = useMutation({
    mutationFn: () =>
      api.patchDocument(docId, {
        name,
        tags: tags.split(",").map((s) => s.trim()).filter(Boolean),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["document", docId] });
      void qc.invalidateQueries({ queryKey: ["documents"] });
    },
  });
  const remove = useMutation({
    mutationFn: () => api.deleteDocument(docId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["documents"] });
      navigate("/");
    },
  });

  if (doc.isLoading) return <p className="p-6 text-sm text-muted">{t("common.loading")}</p>;
  if (doc.error || !doc.data || !current) {
    return (
      <p role="alert" className="p-6 text-sm text-danger">
        {t("document.notFound")}
      </p>
    );
  }

  const use = (toolId: string) => {
    const ref: InputRef = {
      key: uid(),
      name: current.filename,
      versionId: current.id,
      pages: current.pages,
      size: current.size,
    };
    navigate(toolPath(toolId, current.id), { state: { inputs: [ref] } });
  };
  const toolTitle = (id: string | null) =>
    id ? t(`tools.${id}.title`, { defaultValue: tools?.find((x) => x.id === id)?.title ?? id }) : null;

  return (
    <div className="mx-auto grid max-w-6xl gap-6 p-4 sm:p-6 lg:grid-cols-[1fr_22rem]">
      <section aria-labelledby="doc-title" className="min-w-0">
        <h1 id="doc-title" className="font-display truncate text-3xl font-semibold">
          {doc.data.name}
        </h1>
        <p className="tabular mt-1 text-sm text-muted">
          {t("document.viewing")}: {t("common.version", { n: current.seq })} · {formatBytes(current.size)}
        </p>

        {current.encrypted ? (
          <p className={`${cardClass} mt-4 p-4 text-sm`}>{t("document.encryptedNote")}</p>
        ) : (
          <iframe
            title={`${t("document.preview")}: ${doc.data.name}`}
            src={api.versionDownloadUrl(current.id, true)}
            className="mt-4 h-[70vh] w-full rounded-2xl border border-border bg-white shadow-card"
          />
        )}
      </section>

      <div className="grid content-start gap-6">
        <section className={`${cardClass} p-4 shadow-card`} aria-labelledby="meta-edit">
          <h2 id="meta-edit" className="font-display mb-3 text-lg font-semibold">
            {t("document.rename")}
          </h2>
          <form
            className="grid gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              save.mutate();
            }}
          >
            <div>
              <label htmlFor="doc-name" className={labelClass}>
                {t("document.rename")}
              </label>
              <input id="doc-name" className={inputClass} value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div>
              <label htmlFor="doc-tags" className={labelClass}>
                {t("document.tags")}
              </label>
              <input id="doc-tags" className={inputClass} value={tags} onChange={(e) => setTags(e.target.value)} aria-describedby="tags-hint" />
              <p id="tags-hint" className={hintClass}>
                {t("document.tagsHint")}
              </p>
            </div>
            <div className="flex gap-2">
              <Button type="submit" variant="primary" disabled={save.isPending}>
                {t("common.save")}
              </Button>
              <Button variant="danger" onClick={() => window.confirm(t("library.confirmDelete", { name: doc.data!.name })) && remove.mutate()}>
                {t("common.delete")}
              </Button>
            </div>
            {save.isError && (
              <p role="alert" className="text-sm text-danger">
                {errorText(t, save.error)}
              </p>
            )}
          </form>
        </section>

        <section className={`${cardClass} p-4 shadow-card`} aria-labelledby="actions-h">
          <h2 id="actions-h" className="font-display mb-3 text-lg font-semibold">
            {t("document.actions")}
          </h2>
          <ul className="flex flex-wrap gap-2">
            {sortByGroup(tools ?? [])
              .filter((x) => x.accepts !== "image")
              .filter((x) => !current.encrypted || x.id === "unlock")
              .map((x) => (
                <li key={x.id} data-group={isKnownGroup(x.group) ? x.group : "none"}>
                  <Button size="sm" className="border-l-4 border-l-g" onClick={() => use(x.id)}>
                    <ToolIcon toolId={x.id} group={x.group} variant="bare" className="h-4 w-4" />
                    {toolTitle(x.id)}
                  </Button>
                </li>
              ))}
          </ul>
        </section>

        <section className={`${cardClass} p-4 shadow-card`} aria-labelledby="hist-h">
          <h2 id="hist-h" className="font-display mb-3 text-lg font-semibold">
            {t("document.versions")}
          </h2>
          <ol className="grid gap-2">
            {[...(versions.data ?? [])].reverse().map((v) => (
              <li key={v.id} className={`rounded-xl border p-2 transition-colors ${v.id === current.id ? "border-text bg-surface-2" : "border-border"}`}>
                <div className="flex items-center justify-between gap-2">
                  <button type="button" className="min-w-0 text-left" onClick={() => setSelected(v.id)} aria-current={v.id === current.id}>
                    <span className="block text-sm font-medium">
                      {t("common.version", { n: v.seq })}
                      {" · "}
                      {v.tool ? t("document.createdBy", { tool: toolTitle(v.tool) }) : t("document.original")}
                    </span>
                    <span className="block text-xs text-muted">
                      {formatDate(v.created_at, i18n.language)} · {formatBytes(v.size)}
                      {v.pages ? ` · ${t("common.pages", { count: v.pages })}` : ""}
                    </span>
                  </button>
                  <a
                    href={api.versionDownloadUrl(v.id)}
                    aria-label={`${t("common.download")}: ${t("common.version", { n: v.seq })}`}
                    className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md hover:bg-surface-2"
                  >
                    <Download aria-hidden className="h-4 w-4" />
                  </a>
                </div>
              </li>
            ))}
          </ol>
        </section>

        <section className={`${cardClass} p-4 shadow-card`} aria-labelledby="props-h">
          <h2 id="props-h" className="font-display mb-3 text-lg font-semibold">
            {t("document.metadata")}
          </h2>
          {meta.data && Object.keys(meta.data.info).length > 0 ? (
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
              {Object.entries(meta.data.info).map(([k, v]) => (
                <div key={k} className="contents">
                  <dt className="text-muted">{k}</dt>
                  <dd className="break-words">{v}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="text-sm text-muted">{t("document.noMeta")}</p>
          )}
        </section>

        <Link to="/" className="text-sm text-accent hover:underline">
          ← {t("library.title")}
        </Link>
      </div>
    </div>
  );
}
