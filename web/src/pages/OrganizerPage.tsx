import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  rectSortingStrategy,
  sortableKeyboardCoordinates,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  Copy,
  FilePlus,
  GripVertical,
  Loader2,
  RotateCcw,
  RotateCw,
  Trash2,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/Button";
import { Thumb } from "@/components/Thumb";
import { cardClass } from "@/components/ui";
import { api } from "@/lib/api";
import { errorText } from "@/lib/errors";
import { uid } from "@/lib/utils";

interface Item {
  key: string;
  source: number | "blank";
  /** Extra clockwise rotation (0/90/180/270) on top of the page's own rotation. */
  rotate: number;
}

const fresh = (n: number): Item[] => Array.from({ length: n }, (_, i) => ({ key: uid(), source: i + 1, rotate: 0 }));

export function OrganizerPage() {
  const { versionId } = useParams();
  return versionId ? <Organizer key={versionId} versionId={versionId} /> : <DocumentChooser />;
}

function DocumentChooser() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { data = [], isLoading } = useQuery({ queryKey: ["documents"], queryFn: api.documents });
  const usable = data.filter((d) => !d.latest_version.encrypted);
  return (
    <div className="mx-auto max-w-3xl p-4 sm:p-6">
      <h1 className="text-2xl font-semibold">{t("organizer.title")}</h1>
      <p className="mt-1 text-sm text-muted">{t("organizer.pickDocument")}</p>
      {isLoading && <p className="mt-4 text-sm text-muted">{t("common.loading")}</p>}
      {!isLoading && usable.length === 0 && <p className="mt-4 text-sm text-muted">{t("toolPage.libraryEmpty")}</p>}
      <ul className="mt-4 grid gap-2">
        {usable.map((d) => (
          <li key={d.id}>
            <button
              type="button"
              onClick={() => navigate(`/organize/${d.latest_version.id}`)}
              className={`${cardClass} flex w-full items-center gap-3 p-2 text-left hover:bg-surface-2`}
            >
              <Thumb src={api.thumbnailUrl(d.latest_version.id, 1, 80)} className="h-14 w-10 rounded border border-border bg-white object-cover" />
              <span className="min-w-0 flex-1 truncate text-sm font-medium">{d.name}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Organizer({ versionId }: { versionId: string }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const version = useQuery({ queryKey: ["version", versionId], queryFn: () => api.version(versionId) });
  const pages = useQuery({
    queryKey: ["pages", versionId],
    queryFn: () => api.pages(versionId),
    enabled: version.data ? !version.data.encrypted : false,
  });
  const [items, setItems] = useState<Item[]>([]);
  const total = pages.data?.length ?? 0;

  useEffect(() => {
    if (total > 0) setItems(fresh(total));
  }, [total]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const changed = useMemo(
    () => items.length !== total || items.some((it, i) => it.source !== i + 1 || it.rotate !== 0),
    [items, total],
  );

  const apply = useMutation({
    mutationFn: async () => {
      const params: Record<string, unknown> = { order: items.map((i) => i.source) };
      if (items.some((i) => i.rotate)) params.rotate = items.map((i) => i.rotate);
      const task = await api.createTask("organize", params);
      try {
        await api.addTaskFile(task.id, { versionId });
        return await api.process(task.id);
      } catch (err) {
        void api.deleteTask(task.id).catch(() => undefined);
        throw err;
      }
    },
    onSuccess: () => {
      const docId = version.data!.document_id;
      void qc.invalidateQueries({ queryKey: ["documents"] });
      void qc.invalidateQueries({ queryKey: ["document", docId] });
      void qc.invalidateQueries({ queryKey: ["versions", docId] });
      navigate(`/library/${docId}`);
    },
  });

  const update = (key: string, fn: (i: Item) => Item) => setItems((cur) => cur.map((i) => (i.key === key ? fn(i) : i)));
  const move = (from: number, to: number) => {
    if (to < 0 || to >= items.length) return;
    setItems((cur) => arrayMove(cur, from, to));
  };
  const onDragEnd = (e: DragEndEvent) => {
    if (!e.over || e.active.id === e.over.id) return;
    move(
      items.findIndex((i) => i.key === e.active.id),
      items.findIndex((i) => i.key === e.over!.id),
    );
  };

  if (version.isLoading) return <p className="p-6 text-sm text-muted">{t("common.loading")}</p>;
  if (version.error || !version.data) {
    return (
      <p role="alert" className="p-6 text-sm text-danger">
        {errorText(t, version.error)}
      </p>
    );
  }
  if (version.data.encrypted) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <h1 className="font-display text-3xl font-semibold">{t("organizer.title")}</h1>
        <p className={`${cardClass} mt-4 p-4 text-sm`}>{t("document.encryptedNote")}</p>
        <Link to={`/library/${version.data.document_id}`} className="mt-4 inline-block text-sm text-accent hover:underline">
          ← {version.data.filename}
        </Link>
      </div>
    );
  }

  return (
    <div data-group="organize" className="mx-auto max-w-6xl p-4 sm:p-6">
      <h1 className="font-display text-3xl font-semibold">{t("organizer.title")}</h1>
      <p className="mt-1 text-sm text-muted">
        {version.data.filename} — {t("organizer.hint")}
      </p>

      <div className="sticky top-0 z-10 -mx-4 mt-4 flex flex-wrap items-center gap-2 border-b border-border bg-bg/95 px-4 py-2 backdrop-blur sm:-mx-6 sm:px-6">
        <Button variant="primary" disabled={!changed || apply.isPending} onClick={() => apply.mutate()}>
          {apply.isPending ? (
            <>
              <Loader2 aria-hidden className="h-4 w-4 animate-spin" />
              {t("common.running")}
            </>
          ) : (
            t("organizer.apply")
          )}
        </Button>
        <Button onClick={() => setItems((cur) => [...cur, { key: uid(), source: "blank", rotate: 0 }])}>
          <FilePlus aria-hidden className="h-4 w-4" />
          {t("organizer.addBlank")}
        </Button>
        <Button variant="ghost" onClick={() => setItems(fresh(total))} disabled={!changed}>
          {t("organizer.reset")}
        </Button>
        <span aria-live="polite" className="ml-auto text-sm text-muted">
          {t("organizer.changed", { count: items.length })}
        </span>
      </div>

      {apply.isError && (
        <p role="alert" className="mt-3 text-sm text-danger">
          {errorText(t, apply.error)}
        </p>
      )}

      {pages.isLoading && <p className="mt-6 text-sm text-muted">{t("common.loading")}</p>}
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
        <SortableContext items={items.map((i) => i.key)} strategy={rectSortingStrategy}>
          <ul aria-label={t("organizer.title")} className="mt-4 grid grid-cols-[repeat(auto-fill,minmax(9.5rem,1fr))] gap-4">
            {items.map((item, index) => (
              <PageCard
                key={item.key}
                item={item}
                index={index}
                last={index === items.length - 1}
                versionId={versionId}
                canDelete={items.length > 1}
                onRotate={(delta) => update(item.key, (i) => ({ ...i, rotate: (i.rotate + delta + 360) % 360 }))}
                onDuplicate={() =>
                  setItems((cur) => {
                    const at = cur.findIndex((i) => i.key === item.key);
                    return [...cur.slice(0, at + 1), { ...item, key: uid() }, ...cur.slice(at + 1)];
                  })
                }
                onDelete={() => setItems((cur) => (cur.length > 1 ? cur.filter((i) => i.key !== item.key) : cur))}
                onMove={move}
              />
            ))}
          </ul>
        </SortableContext>
      </DndContext>
    </div>
  );
}

function PageCard({
  item,
  index,
  last,
  versionId,
  canDelete,
  onRotate,
  onDuplicate,
  onDelete,
  onMove,
}: {
  item: Item;
  index: number;
  last: boolean;
  versionId: string;
  canDelete: boolean;
  onRotate: (delta: number) => void;
  onDuplicate: () => void;
  onDelete: () => void;
  onMove: (from: number, to: number) => void;
}) {
  const { t } = useTranslation();
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging } = useSortable({ id: item.key });
  const label = item.source === "blank" ? t("organizer.blank") : t("organizer.pageLabel", { n: item.source });
  const btn = "h-8 w-8";
  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`${cardClass} group/page relative p-2 shadow-card transition duration-200 hover:-translate-y-1 hover:border-g focus-within:-translate-y-1 focus-within:border-g focus-within:ring-2 focus-within:ring-g motion-reduce:transform-none ${isDragging ? "z-20 scale-105 border-g opacity-90 shadow-2xl" : ""}`}
    >
      <div className="flex aspect-square items-center justify-center overflow-hidden rounded-md bg-surface-2">
        {item.source === "blank" ? (
          <div role="img" aria-label={label} className="flex h-full max-h-full w-3/4 items-center justify-center rounded border border-border bg-white text-xs text-neutral-500" style={{ transform: `rotate(${item.rotate}deg)` }}>
            {label}
          </div>
        ) : (
          <Thumb
            alt={label}
            src={api.thumbnailUrl(versionId, item.source, 240)}
            className="max-h-full max-w-full bg-white object-contain shadow-sm transition-transform"
            fallbackClassName="aspect-[3/4] h-4/5 border border-dashed border-border"
            style={{ transform: `rotate(${item.rotate}deg)` }}
          />
        )}
      </div>
      <p className="tabular mt-1 flex items-center justify-center gap-1.5 text-center text-xs text-muted">
        <span aria-hidden className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-g px-1 font-semibold text-g-fg">{index + 1}</span>
        <span className="sr-only">
          {index + 1}. {label}
        </span>
        <span aria-hidden>{label}</span>
      </p>
      <div className="mt-1 flex flex-wrap justify-center gap-0.5">
        <button
          ref={setActivatorNodeRef}
          type="button"
          aria-label={`${t("common.dragHandle")}: ${label}`}
          className={`${btn} inline-flex cursor-grab touch-none items-center justify-center rounded-md hover:bg-surface-2`}
          {...attributes}
          {...listeners}
        >
          <GripVertical aria-hidden className="h-4 w-4" />
        </button>
        <Button variant="ghost" size="icon" className={btn} aria-label={`${t("organizer.moveLeft")}: ${label}`} disabled={index === 0} onClick={() => onMove(index, index - 1)}>
          <ChevronLeft aria-hidden className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" className={btn} aria-label={`${t("organizer.moveRight")}: ${label}`} disabled={last} onClick={() => onMove(index, index + 1)}>
          <ChevronRight aria-hidden className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" className={btn} aria-label={`${t("organizer.rotateLeft")}: ${label}`} onClick={() => onRotate(-90)}>
          <RotateCcw aria-hidden className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" className={btn} aria-label={`${t("organizer.rotateRight")}: ${label}`} onClick={() => onRotate(90)}>
          <RotateCw aria-hidden className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" className={btn} aria-label={`${t("organizer.duplicate")}: ${label}`} onClick={onDuplicate}>
          <Copy aria-hidden className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" className={btn} aria-label={`${t("organizer.deletePage")}: ${label}`} disabled={!canDelete} onClick={onDelete}>
          <Trash2 aria-hidden className="h-4 w-4 text-danger" />
        </Button>
      </div>
    </li>
  );
}
