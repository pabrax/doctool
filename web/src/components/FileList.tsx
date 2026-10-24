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
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { ArrowDown, ArrowUp, FileText, GripVertical, Lock, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { InputRef } from "@/lib/types";
import { formatBytes } from "@/lib/utils";
import { Button } from "./Button";

interface Props {
  items: InputRef[];
  onChange: (items: InputRef[]) => void;
  /** Keys of files that need a password; rendered as an inline field. */
  needPassword?: Set<string>;
  passwords?: Record<string, string>;
  onPassword?: (key: string, value: string) => void;
}

export function FileList({ items, onChange, needPassword, passwords = {}, onPassword }: Props) {
  const { t } = useTranslation();
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
  const move = (from: number, to: number) => {
    if (to < 0 || to >= items.length) return;
    onChange(arrayMove(items, from, to));
  };
  const onDragEnd = (e: DragEndEvent) => {
    if (!e.over || e.active.id === e.over.id) return;
    move(
      items.findIndex((i) => i.key === e.active.id),
      items.findIndex((i) => i.key === e.over!.id),
    );
  };

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
      <SortableContext items={items.map((i) => i.key)} strategy={verticalListSortingStrategy}>
        <ul className="grid gap-2" aria-label={t("toolPage.files")}>
          {items.map((item, index) => (
            <Row
              key={item.key}
              item={item}
              index={index}
              last={index === items.length - 1}
              onMove={move}
              onRemove={() => onChange(items.filter((i) => i.key !== item.key))}
              askPassword={needPassword?.has(item.key)}
              password={passwords[item.key] ?? ""}
              onPassword={(v) => onPassword?.(item.key, v)}
              t={t}
            />
          ))}
        </ul>
      </SortableContext>
    </DndContext>
  );
}

function Row({
  item,
  index,
  last,
  onMove,
  onRemove,
  askPassword,
  password,
  onPassword,
  t,
}: {
  item: InputRef;
  index: number;
  last: boolean;
  onMove: (from: number, to: number) => void;
  onRemove: () => void;
  askPassword?: boolean;
  password: string;
  onPassword: (v: string) => void;
  t: (k: string, o?: Record<string, unknown>) => string;
}) {
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging } =
    useSortable({ id: item.key });
  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`rise-in rounded-xl border border-l-4 border-border border-l-g bg-surface px-2 py-2 shadow-card ${isDragging ? "opacity-70 shadow-lg" : ""}`}
    >
      <div className="flex items-center gap-2">
        <button
          ref={setActivatorNodeRef}
          type="button"
          aria-label={`${t("common.dragHandle")}: ${item.name}`}
          className="cursor-grab touch-none rounded p-1 text-muted hover:bg-surface-2"
          {...attributes}
          {...listeners}
        >
          <GripVertical aria-hidden className="h-4 w-4" />
        </button>
        <FileText aria-hidden className="h-4 w-4 shrink-0 text-g-ink" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{item.name}</p>
          <p className="tabular text-xs text-muted">
            {[item.pages ? t("common.pages", { count: item.pages }) : null, item.size ? formatBytes(item.size) : null]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        <Button variant="ghost" size="icon" aria-label={`${t("common.moveUp")}: ${item.name}`} disabled={index === 0} onClick={() => onMove(index, index - 1)}>
          <ArrowUp aria-hidden className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" aria-label={`${t("common.moveDown")}: ${item.name}`} disabled={last} onClick={() => onMove(index, index + 1)}>
          <ArrowDown aria-hidden className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" aria-label={`${t("common.remove")}: ${item.name}`} onClick={onRemove}>
          <X aria-hidden className="h-4 w-4" />
        </Button>
      </div>
      {askPassword && (
        <div className="mt-2 flex items-center gap-2 pl-8">
          <Lock aria-hidden className="h-4 w-4 text-danger" />
          <input
            type="password"
            autoComplete="off"
            aria-label={t("toolPage.passwordFor", { name: item.name })}
            placeholder={t("params.password")}
            className="w-full max-w-xs rounded-md border border-danger/50 bg-surface px-2 py-1 text-sm"
            value={password}
            onChange={(e) => onPassword(e.target.value)}
          />
        </div>
      )}
    </li>
  );
}
