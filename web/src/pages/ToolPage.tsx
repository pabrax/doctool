import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, Download, Loader2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, Navigate, useLocation, useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/Button";
import { Dropzone } from "@/components/Dropzone";
import { FileList } from "@/components/FileList";
import { LibraryPicker } from "@/components/LibraryPicker";
import { SchemaForm, defaultsFor, type FormValue } from "@/components/SchemaForm";
import { cardClass } from "@/components/ui";
import { api } from "@/lib/api";
import { errorText, isWrongPassword } from "@/lib/errors";
import type { Doc, InputRef, Task, Tool } from "@/lib/types";
import { toolPath, useTools } from "@/lib/useTools";
import { uid } from "@/lib/utils";

export function ToolPage() {
  const { toolId } = useParams();
  const { data: tools } = useTools();
  const tool = tools?.find((t) => t.id === toolId);
  const { t } = useTranslation();
  if (toolId === "organize") return <Navigate to="/organize" replace />;
  if (!tools) return <p className="p-6 text-sm text-muted">{t("common.loading")}</p>;
  if (!tool) return <Navigate to="/" replace />;
  // `key` resets the page state whenever the user switches tool.
  return <ToolWorkspace key={tool.id} tool={tool} tools={tools} />;
}

function ToolWorkspace({ tool, tools }: { tool: Tool; tools: Tool[] }) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const qc = useQueryClient();
  const initial = (location.state as { inputs?: InputRef[] } | null)?.inputs ?? [];

  const [inputs, setInputs] = useState<InputRef[]>(initial);
  const [params, setParams] = useState<FormValue>(() => defaultsFor(tool.params_schema));
  const [passwords, setPasswords] = useState<Record<string, string>>({});
  const [pickerOpen, setPickerOpen] = useState(false);
  const [needPassword, setNeedPassword] = useState<Set<string>>(new Set());

  const single = tool.max_files === 1;
  const acceptsPdf = tool.accepts !== "image";
  const title = t(`tools.${tool.id}.title`, { defaultValue: tool.title });
  const description = t(`tools.${tool.id}.description`, { defaultValue: tool.description });

  useEffect(() => {
    document.title = `${title} · doctool`;
  }, [title, i18n.language]);

  const addFiles = (files: File[]) => {
    const next = files.map<InputRef>((file) => ({ key: uid(), name: file.name, file, size: file.size }));
    setInputs((cur) => (single ? next.slice(0, 1) : [...cur, ...next]));
  };
  const addDoc = (doc: Doc) => {
    const v = doc.latest_version;
    const ref: InputRef = { key: uid(), name: v.filename, versionId: v.id, pages: v.pages, size: v.size };
    setInputs((cur) => (single ? [ref] : [...cur, ref]));
  };

  const run = useMutation<Task, unknown, void>({
    mutationFn: async () => {
      const task = await api.createTask(tool.id, params);
      try {
        const ids: Record<string, string> = {};
        for (const input of inputs) {
          const t2 = await api.addTaskFile(task.id, input.file ? { file: input.file } : { versionId: input.versionId });
          ids[input.key] = t2.files.filter((f) => f.role === "in").at(-1)!.id;
        }
        const pw: Record<string, string> = {};
        for (const [key, value] of Object.entries(passwords)) if (value && ids[key]) pw[ids[key]] = value;
        return await api.process(task.id, pw);
      } catch (err) {
        void api.deleteTask(task.id).catch(() => undefined);
        throw err;
      }
    },
    onSuccess: () => {
      setNeedPassword(new Set());
      void qc.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: (err) => {
      if (isWrongPassword(err)) {
        // Any PDF could be the culprit; ask for all that look encrypted or have no password yet.
        setNeedPassword(new Set(inputs.filter((i) => !i.file || i.file.type === "application/pdf").map((i) => i.key)));
      }
    },
  });

  const missing = Math.max(0, tool.min_files - inputs.length);
  const canRun = missing === 0 && !run.isPending;
  const result = run.data;
  const outputs = useMemo(() => result?.files.filter((f) => f.role === "out") ?? [], [result]);
  const firstVersionId = outputs.find((f) => f.version_id)?.version_id ?? null;
  const { data: outVersion } = useQuery({
    queryKey: ["version", firstVersionId],
    queryFn: () => api.version(firstVersionId!),
    enabled: !!firstVersionId,
  });

  const useElsewhere = (toolId: string) => {
    if (!outVersion) return;
    const ref: InputRef = {
      key: uid(),
      name: outVersion.filename,
      versionId: outVersion.id,
      pages: outVersion.pages,
      size: outVersion.size,
    };
    navigate(toolPath(toolId, outVersion.id), { state: { inputs: [ref] } });
  };

  return (
    <div className="mx-auto max-w-5xl p-4 sm:p-6">
      <h1 className="text-2xl font-semibold">{title}</h1>
      <p className="mt-1 text-sm text-muted">{description}</p>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_20rem]">
        <section aria-labelledby="files-h" className="grid content-start gap-4">
          <h2 id="files-h" className="sr-only">
            {t("toolPage.files")}
          </h2>
          <Dropzone
            accepts={tool.accepts}
            multiple={!single}
            compact={inputs.length > 0}
            onFiles={addFiles}
            extra={
              acceptsPdf ? (
                <Button onClick={() => setPickerOpen(true)}>{t("dropzone.fromLibrary")}</Button>
              ) : null
            }
          />
          {inputs.length > 0 ? (
            <FileList
              items={inputs}
              onChange={setInputs}
              needPassword={needPassword}
              passwords={passwords}
              onPassword={(key, v) => setPasswords((p) => ({ ...p, [key]: v }))}
            />
          ) : (
            <p className="text-sm text-muted">{t("toolPage.noFiles")}</p>
          )}
        </section>

        <aside aria-labelledby="options-h" className={`${cardClass} h-fit p-4`}>
          <h2 id="options-h" className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted">
            {t("toolPage.options")}
          </h2>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (canRun) run.mutate();
            }}
            className="grid gap-4"
          >
            <SchemaForm toolId={tool.id} schema={tool.params_schema} value={params} onChange={setParams} />
            {missing > 0 && <p className="text-xs text-muted">{t("toolPage.needFiles", { min: tool.min_files })}</p>}
            <Button type="submit" variant="primary" disabled={!canRun}>
              {run.isPending ? (
                <>
                  <Loader2 aria-hidden className="h-4 w-4 animate-spin" />
                  {t("common.running")}
                </>
              ) : needPassword.size > 0 ? (
                t("common.retry")
              ) : (
                t("common.run")
              )}
            </Button>
          </form>
        </aside>
      </div>

      <div aria-live="polite" className="mt-6">
        {run.isError && (
          <div role="alert" className="flex items-start gap-2 rounded-lg border border-danger/40 bg-danger-soft p-3 text-sm text-danger">
            <AlertCircle aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-medium">
                {isWrongPassword(run.error) ? t("toolPage.passwordNeeded") : errorText(t, run.error)}
              </p>
              {isWrongPassword(run.error) && <p>{errorText(t, run.error)}</p>}
            </div>
          </div>
        )}
        {result && result.state === "success" && (
          <section aria-labelledby="result-h" className={`${cardClass} p-4`}>
            <h2 id="result-h" className="flex items-center gap-2 text-base font-semibold text-ok">
              <CheckCircle2 aria-hidden className="h-5 w-5" />
              {t("toolPage.resultTitle")}
            </h2>
            <p className="mt-1 text-sm text-muted">
              {outputs.length > 1
                ? t("toolPage.multipleOutputs", { count: outputs.length })
                : outputs[0]?.filename}
              {firstVersionId ? ` — ${t("toolPage.resultSaved")}` : ""}
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <a
                href={api.taskDownloadUrl(result.id)}
                className="inline-flex min-h-9 items-center gap-2 rounded-md bg-accent px-3.5 py-2 text-sm font-medium text-accent-fg hover:brightness-110"
              >
                <Download aria-hidden className="h-4 w-4" />
                {outputs.length > 1 ? t("common.downloadZip") : t("common.download")}
              </a>
              {outVersion && (
                <Link
                  to={`/library/${outVersion.document_id}`}
                  className="inline-flex min-h-9 items-center rounded-md border border-border bg-surface px-3.5 py-2 text-sm font-medium hover:bg-surface-2"
                >
                  {t("toolPage.openInLibrary")}
                </Link>
              )}
              {outVersion && !outVersion.encrypted && (
                <label className="text-sm">
                  <span className="sr-only">{t("toolPage.useAsInput")}</span>
                  <select
                    className="min-h-9 rounded-md border border-border bg-surface px-2 text-sm"
                    value=""
                    onChange={(e) => e.target.value && useElsewhere(e.target.value)}
                  >
                    <option value="">{t("toolPage.useAsInput")}…</option>
                    {tools
                      .filter((x) => x.accepts !== "image")
                      .map((x) => (
                        <option key={x.id} value={x.id}>
                          {t(`tools.${x.id}.title`, { defaultValue: x.title })}
                        </option>
                      ))}
                  </select>
                </label>
              )}
            </div>
          </section>
        )}
      </div>

      <LibraryPicker open={pickerOpen} onClose={() => setPickerOpen(false)} onPick={addDoc} />
    </div>
  );
}
