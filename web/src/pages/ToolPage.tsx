import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, Download, Info, Loader2, PlugZap, TriangleAlert } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, Navigate, useLocation, useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/Button";
import { Dropzone } from "@/components/Dropzone";
import { FileList } from "@/components/FileList";
import { LibraryPicker } from "@/components/LibraryPicker";
import { SchemaForm, defaultsFor, type FormValue } from "@/components/SchemaForm";
import { ToolIcon } from "@/components/ToolIcon";
import { cardClass } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { isKnownGroup, toolIcon } from "@/lib/toolIcons";
import { errorText, isBusy, isWrongPassword } from "@/lib/errors";
import type { Doc, InputRef, Task, TaskWarning, Tool } from "@/lib/types";
import { takesPdf, toolPath, useTools } from "@/lib/useTools";
import { nextSteps } from "@/lib/nextSteps";
import { grownPercent, savedPercent } from "@/lib/savings";
import { formatBytes, uid } from "@/lib/utils";

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

/** Where the engine set-up is explained (engine-missing banner). */
const ENGINE_HELP_URL = "https://github.com/pabrax/doctool/blob/main/docs/office-setup.md";

/** One finished-task warning as a sentence, plus a link when it names a tool that exists. */
function WarningItem({ warning, tools }: { warning: TaskWarning; tools: Tool[] }) {
  const { t } = useTranslation();
  const text = t(`warnings.${warning.code}`, {
    ...(warning.params ?? {}),
    defaultValue: t("warnings.generic"),
    interpolation: { escapeValue: false },
  });
  const target = warning.action ? tools.find((x) => x.id === warning.action!.tool) : undefined;
  return (
    <li className="flex items-start gap-2">
      <TriangleAlert aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
      <span>
        {warning.file ? `${warning.file}: ` : ""}
        {text}{" "}
        {target && (
          <Link to={toolPath(target.id)} className="font-medium underline underline-offset-2">
            {t("toolPage.openTool", { tool: t(`tools.${target.id}.title`, { defaultValue: target.title }) })}
          </Link>
        )}
      </span>
    </li>
  );
}

/** Tools whose result card compares the size before and after. */
const SIZE_LINE_TOOLS = ["compress", "imagecompress", "imageresize", "imageconvert", "imageclean"];

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
  /** Size of the single input at the moment the task succeeded (for the "x% smaller" line). */
  const [sizeBefore, setSizeBefore] = useState<number | null>(null);
  const resultRef = useRef<HTMLHeadingElement>(null);
  const undoRef = useRef<HTMLButtonElement>(null);
  /** What "Remove all" took away, so it can be put back. */
  const [removed, setRemoved] = useState<{ inputs: InputRef[]; passwords: Record<string, string> } | null>(null);

  const single = tool.max_files === 1;
  const acceptsPdf = takesPdf(tool);
  const engineOk = tool.available !== false;
  const title = t(`tools.${tool.id}.title`, { defaultValue: tool.title });
  const description = t(`tools.${tool.id}.description`, { defaultValue: tool.description });
  /** Honest-quality note shown before running (PDF -> Office tools). */
  const note = t(`tools.${tool.id}.note`, { defaultValue: "" });

  useEffect(() => {
    document.title = `${title} · doctool`;
  }, [title, i18n.language]);

  const addFiles = (files: File[]) => {
    const next = files.map<InputRef>((file) => ({ key: uid(), name: file.name, file, size: file.size }));
    setRemoved(null);
    setInputs((cur) => (single ? next.slice(0, 1) : [...cur, ...next]));
  };
  const addDoc = (doc: Doc) => {
    const v = doc.latest_version;
    const ref: InputRef = { key: uid(), name: v.filename, versionId: v.id, pages: v.pages, size: v.size };
    setRemoved(null);
    setInputs((cur) => (single ? [ref] : [...cur, ref]));
  };
  const clearAll = () => {
    setRemoved({ inputs, passwords });
    setInputs([]);
    setPasswords({});
    setNeedPassword(new Set());
  };
  const undoClear = () => {
    if (!removed) return;
    setInputs(removed.inputs);
    setPasswords(removed.passwords);
    setRemoved(null);
  };
  // The button that was clicked is gone after "Remove all": hand focus to "Undo" so keyboard users are not dropped.
  useEffect(() => {
    if (removed) undoRef.current?.focus();
  }, [removed]);

  /** Set synchronously on submit so a rapid double click cannot start two tasks before `isPending` renders. */
  const submitting = useRef(false);
  const run = useMutation<Task, unknown, void>({
    mutationFn: async () => {
      const task = await api.createTask(tool.id, params);
      try {
        const ids: Record<string, string> = {};
        for (const input of inputs) {
          let t2: Task;
          try {
            t2 = await api.addTaskFile(task.id, input.file ? { file: input.file } : { versionId: input.versionId });
          } catch (err) {
            // Say which file was rejected; the files stay listed so the user can remove it and retry.
            if (err instanceof ApiError && err.state !== "network") err.file = input.name;
            throw err;
          }
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
      setSizeBefore(inputs.length === 1 ? (inputs[0].size ?? null) : null);
      setNeedPassword(new Set());
      void qc.invalidateQueries({ queryKey: ["documents"] });
    },
    onSettled: () => {
      submitting.current = false;
    },
    onError: (err) => {
      if (isWrongPassword(err)) {
        // Any PDF could be the culprit; ask for all that look encrypted or have no password yet.
        setNeedPassword(new Set(inputs.filter((i) => !i.file || i.file.type === "application/pdf").map((i) => i.key)));
      }
    },
  });

  const missing = Math.max(0, tool.min_files - inputs.length);
  const totalSize = inputs.reduce((n, i) => n + (i.size ?? 0), 0);
  const pagesKnown = inputs.length > 0 && inputs.every((i) => typeof i.pages === "number");
  const totalPages = inputs.reduce((n, i) => n + (i.pages ?? 0), 0);
  const summary = [
    t("toolPage.fileCount", { count: inputs.length }),
    pagesKnown ? t("common.pages", { count: totalPages }) : null,
    totalSize > 0 ? formatBytes(totalSize) : null,
  ]
    .filter(Boolean)
    .join(" · ");
  const extra = tool.max_files != null ? Math.max(0, inputs.length - tool.max_files) : 0;
  const canRun = missing === 0 && extra === 0 && !run.isPending && engineOk;
  const result = run.data;
  const outputs = useMemo(() => result?.files.filter((f) => f.role === "out") ?? [], [result]);
  const warnings = result?.warnings ?? [];
  const firstVersionId = outputs.find((f) => f.version_id)?.version_id ?? null;
  const { data: outVersion } = useQuery({
    queryKey: ["version", firstVersionId],
    queryFn: () => api.version(firstVersionId!),
    enabled: !!firstVersionId,
  });

  /** Size of the single output: from the library version (PDFs) or from the task file (images, no version). */
  const outSize = outVersion ? outVersion.size : outputs.length === 1 && !firstVersionId ? (outputs[0].size ?? null) : null;

  /** "x% smaller" for the size-comparing tools; null falls back to the plain size. */
  const sizeLine = (() => {
    if (outSize === null || !sizeBefore || !SIZE_LINE_TOOLS.includes(tool.id)) return null;
    const before = formatBytes(sizeBefore);
    const after = formatBytes(outSize);
    const saved = savedPercent(sizeBefore, outSize);
    if (saved !== null) return t("toolPage.smaller", { pct: saved, before, after });
    if (tool.id === "compress") return t("toolPage.notSmaller", { before, after });
    if (tool.id === "imagecompress") {
      // savedPercent is null under 1%: only say "kept as it was" when the result really is not smaller.
      return outSize < sizeBefore ? t("toolPage.smallerTiny", { before, after }) : t("toolPage.imageKept", { after });
    }
    const grown = tool.id === "imageresize" || tool.id === "imageconvert" ? grownPercent(sizeBefore, outSize) : null;
    return grown !== null ? t("toolPage.larger", { pct: grown, before, after }) : null;
  })();

  const steps = useMemo(() => nextSteps(tool.id, tools), [tool.id, tools]);
  const succeeded = result?.state === "success";
  // The result can land below the fold (mobile stacks files, options, result). Scroll it into view only when it
  // is not already visible. Focus stays where it is (on Run, so "run again" is one key away) and the
  // existing aria-live region announces the result, so screen readers do not hear it twice.
  useEffect(() => {
    const el = resultRef.current;
    if (!succeeded || !el) return;
    const r = el.getBoundingClientRect();
    if (r.top >= 0 && r.bottom <= window.innerHeight) return;
    const calm = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    el.scrollIntoView?.({ block: "nearest", behavior: calm ? "auto" : "smooth" });
  }, [succeeded, result?.id]);

  const startOver = () => {
    run.reset();
    setInputs([]);
    setPasswords({});
    setNeedPassword(new Set());
    setSizeBefore(null);
    document.getElementById("main")?.focus();
  };

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
    <div data-group={isKnownGroup(tool.group) ? tool.group : "none"} className="mx-auto max-w-5xl p-4 sm:p-6">
      <header className="flex items-center gap-4 rounded-2xl border border-border border-l-[6px] border-l-g bg-g-soft p-4 sm:p-5">
        <span aria-hidden className="inline-flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-g text-g-fg shadow-sm">
          {(() => {
            const Icon = toolIcon(tool.id);
            return <Icon className="h-7 w-7" />;
          })()}
        </span>
        <div className="min-w-0">
          <p className="text-xs font-semibold text-g-ink">{t(`groups.${tool.group}`, { defaultValue: tool.group })}</p>
          <h1 className="font-display text-2xl font-semibold sm:text-3xl">{title}</h1>
          <p className="mt-0.5 text-sm text-muted">{description}</p>
        </div>
      </header>

      {note && (
        <p role="note" className="mt-4 flex items-start gap-2 rounded-lg border border-border border-l-4 bg-surface p-3 text-sm">
          <Info aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
          <span>{note}</span>
        </p>
      )}
      {!engineOk && (
        <p role="status" className="mt-4 flex items-start gap-2 rounded-lg border border-dashed border-border bg-surface-2 p-3 text-sm">
          <PlugZap aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
          <span>
            {t("toolPage.engineMissing")}{" "}
            <a href={ENGINE_HELP_URL} className="inline-block min-h-6 font-medium underline underline-offset-2">
              {t("toolPage.engineHow")}
            </a>
          </span>
        </p>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_20rem]">
        <section aria-labelledby="files-h" className="grid content-start gap-4">
          <h2 id="files-h" className="sr-only">
            {t("toolPage.files")}
          </h2>
          <Dropzone
            accepts={tool.accepts}
            extensions={tool.extensions}
            disabled={!engineOk}
            group={tool.group}
            multiple={!single}
            compact={inputs.length > 0}
            onFiles={addFiles}
            extra={
              acceptsPdf ? (
                <Button onClick={() => setPickerOpen(true)}>{t("dropzone.fromLibrary")}</Button>
              ) : null
            }
          />
          {/* Always mounted so the announcement is reliable; its text appears when files are removed. */}
          <div role="status" className="sr-only">
            {removed && inputs.length === 0 ? t("toolPage.removedAll") : ""}
          </div>
          {inputs.length > 0 ? (
            <>
              <div className="flex items-center justify-between gap-2">
                <p className="tabular text-sm font-medium">{summary}</p>
                {inputs.length > 1 && (
                  <Button variant="ghost" size="sm" onClick={clearAll}>
                    {t("toolPage.clearAll")}
                  </Button>
                )}
              </div>
              <FileList
                items={inputs}
                onChange={setInputs}
                needPassword={needPassword}
                passwords={passwords}
                onPassword={(key, v) => setPasswords((p) => ({ ...p, [key]: v }))}
              />
            </>
          ) : removed ? (
            <div className="flex items-center justify-between gap-2 text-sm">
              <p id="removed-msg" aria-hidden>
                {t("toolPage.removedAll")}
              </p>
              <Button ref={undoRef} aria-describedby="removed-msg" size="sm" onClick={undoClear}>
                {t("toolPage.undo")}
              </Button>
            </div>
          ) : (
            <p className="text-sm text-muted">{t("toolPage.noFiles")}</p>
          )}
        </section>

        <aside aria-labelledby="options-h" className={`${cardClass} h-fit p-4 shadow-card`}>
          <h2 id="options-h" className="font-display mb-3 text-lg font-semibold">
            {t("toolPage.options")}
          </h2>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!canRun || submitting.current) return;
              submitting.current = true;
              run.mutate();
            }}
            className="grid gap-4"
          >
            <SchemaForm toolId={tool.id} schema={tool.params_schema} value={params} onChange={setParams} />
            {missing > 0 && <p className="text-xs text-muted">{t("toolPage.needMore", { count: missing })}</p>}
            {extra > 0 && (
              <p className="text-xs text-danger">
                {t(tool.accepts === "image" ? "toolPage.tooManyImages" : "toolPage.tooManyFiles", { max: tool.max_files, extra })}
              </p>
            )}
            <Button type="submit" variant="primary" disabled={!canRun}>
              {run.isPending ? (
                <>
                  <Loader2 aria-hidden className="h-4 w-4 animate-spin" />
                  {t("common.running")}
                </>
              ) : needPassword.size > 0 || (run.isError && isBusy(run.error) && tool.group === "office") ? (
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
                {isWrongPassword(run.error) ? t("toolPage.passwordNeeded") : errorText(t, run.error, tool.id, tool.max_files)}
              </p>
              {isWrongPassword(run.error) && <p>{errorText(t, run.error, tool.id, tool.max_files)}</p>}
            </div>
          </div>
        )}
        {result && result.state === "success" && (
          <section aria-labelledby="result-h" className={`${cardClass} rise-in border-ok/50 p-5 shadow-card`}>
            <h2 id="result-h" ref={resultRef} className="font-display flex items-center gap-2 text-xl font-semibold text-ok">
              <CheckCircle2 aria-hidden className="h-5 w-5" />
              {warnings.length ? t("toolPage.resultWarn", { count: warnings.length }) : t("toolPage.resultTitle")}
            </h2>
            <p className="mt-1 text-sm text-muted">
              {outputs.length > 1
                ? t("toolPage.multipleOutputs", { count: outputs.length })
                : outputs[0]?.filename}
              {firstVersionId ? ` — ${t("toolPage.resultSaved")}` : ""}
            </p>
            {outSize !== null && outputs.length === 1 && (
              <p className="tabular mt-1 text-sm font-medium">
                {sizeLine ??
                  [outVersion?.pages ? t("common.pages", { count: outVersion.pages }) : null, formatBytes(outSize)]
                    .filter(Boolean)
                    .join(" · ")}
              </p>
            )}
            {warnings.length > 0 && (
              <div className="mt-3">
                <h3 id="warn-h" className="text-sm font-semibold">
                  {t("toolPage.warningsTitle")}
                </h3>
                <ul aria-labelledby="warn-h" className="mt-1 grid gap-1 text-sm">
                  {warnings.map((w, i) => (
                    <WarningItem key={`${w.code}-${i}`} warning={w} tools={tools} />
                  ))}
                </ul>
              </div>
            )}
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <a
                href={api.taskDownloadUrl(result.id)}
                className="inline-flex min-h-10 items-center gap-2 rounded-lg bg-g px-4 py-2 text-sm font-medium text-g-fg shadow-sm transition hover:brightness-95 active:translate-y-px"
              >
                <Download aria-hidden className="h-4 w-4" />
                {outputs.length > 1 ? t("common.downloadZip") : t("common.download")}
              </a>
              {outVersion && (
                <Link
                  to={`/library/${outVersion.document_id}`}
                  className="inline-flex min-h-10 items-center rounded-lg border border-border bg-surface px-4 py-2 text-sm font-medium hover:bg-surface-2"
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
                      .filter(takesPdf)
                      .map((x) => (
                        <option key={x.id} value={x.id}>
                          {t(`tools.${x.id}.title`, { defaultValue: x.title })}
                        </option>
                      ))}
                  </select>
                </label>
              )}
              <Button variant="ghost" onClick={startOver}>
                {t("toolPage.startOver")}
              </Button>
            </div>
            {outVersion && outputs.length === 1 && !outVersion.encrypted && steps.length > 0 && (
              <div className="mt-4 border-t border-border pt-3">
                <p id="next-h" className="text-xs font-semibold text-muted">
                  {t("toolPage.nextSteps")}
                </p>
                <ul aria-labelledby="next-h" className="mt-2 flex flex-wrap gap-2">
                  {steps.map((x) => (
                    <li key={x.id} data-group={isKnownGroup(x.group) ? x.group : "none"}>
                      <Button size="sm" className="border-l-4 border-l-g" onClick={() => useElsewhere(x.id)}>
                        <ToolIcon toolId={x.id} group={x.group} variant="bare" className="h-4 w-4" />
                        {t(`tools.${x.id}.title`, { defaultValue: x.title })}
                      </Button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        )}
      </div>

      <LibraryPicker open={pickerOpen} onClose={() => setPickerOpen(false)} onPick={addDoc} />
    </div>
  );
}
