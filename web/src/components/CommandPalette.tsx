import { useQuery } from "@tanstack/react-query";
import { Command } from "cmdk";
import { FileText, Library } from "lucide-react";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { toolPath, useTools } from "@/lib/useTools";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const item =
  "flex cursor-pointer items-center gap-2 rounded-md px-3 py-2 text-sm text-text aria-selected:bg-accent-soft aria-selected:text-accent";
const heading = "[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:text-muted";

export function CommandPalette({ open, onOpenChange }: Props) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { data: tools = [] } = useTools();
  const { data: docs = [] } = useQuery({ queryKey: ["documents"], queryFn: api.documents, enabled: open });

  // Global shortcut: Ctrl/Cmd+K toggles the palette.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        onOpenChange(!open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onOpenChange]);

  const go = (path: string) => {
    onOpenChange(false);
    navigate(path);
  };

  return (
    <Command.Dialog
      open={open}
      onOpenChange={onOpenChange}
      label={t("nav.palette")}
      overlayClassName="fixed inset-0 z-40 bg-black/50"
      contentClassName="fixed left-1/2 top-[15vh] z-50 w-[min(36rem,92vw)] -translate-x-1/2 overflow-hidden rounded-xl border border-border bg-surface shadow-2xl"
    >
      <Command.Input
        placeholder={t("palette.placeholder")}
        className="w-full border-b border-border bg-transparent px-4 py-3 text-sm text-text outline-none placeholder:text-muted"
      />
      <Command.List className={`max-h-[50vh] overflow-auto p-2 ${heading}`}>
        <Command.Empty className="px-3 py-6 text-center text-sm text-muted">{t("palette.empty")}</Command.Empty>
        <Command.Group heading={t("palette.go")}>
          <Command.Item className={item} value={t("nav.library")} onSelect={() => go("/")}>
            <Library aria-hidden className="h-4 w-4" />
            {t("nav.library")}
          </Command.Item>
        </Command.Group>
        <Command.Group heading={t("palette.tools")}>
          {tools.map((x) => {
            const title = t(`tools.${x.id}.title`, { defaultValue: x.title });
            return (
              <Command.Item key={x.id} className={item} value={`${title} ${x.id}`} onSelect={() => go(toolPath(x.id))}>
                <FileText aria-hidden className="h-4 w-4" />
                {title}
              </Command.Item>
            );
          })}
        </Command.Group>
        {docs.length > 0 && (
          <Command.Group heading={t("palette.documents")}>
            {docs.map((d) => (
              <Command.Item key={d.id} className={item} value={`${d.name} ${d.tags.join(" ")}`} onSelect={() => go(`/library/${d.id}`)}>
                <FileText aria-hidden className="h-4 w-4" />
                {d.name}
              </Command.Item>
            ))}
          </Command.Group>
        )}
      </Command.List>
    </Command.Dialog>
  );
}
