import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Button } from "@/components/Button";
import { ToolIcon } from "@/components/ToolIcon";
import { isKnownGroup } from "@/lib/toolIcons";
import { sortByGroup, toolPath, useTools } from "@/lib/useTools";

/**
 * Home launcher: every tool as a tile, ordered by group, colored by group.
 * Icon and group name are always visible text (never color alone). The two-line description shows from 640px up.
 * On phones the grid defaults to two compact columns (so the library is not pushed off-screen) and a
 * "Show descriptions" toggle switches to one column with descriptions, right where the choice is made.
 * No `title` tooltip (invisible on touch).
 */
export function ToolLauncher() {
  const { t } = useTranslation();
  const { data: tools, isLoading } = useTools();
  const ordered = sortByGroup(tools ?? []);
  const [detail, setDetail] = useState(false); // phones only: one column with descriptions

  return (
    <section aria-labelledby="launcher-h">
      <div className="flex items-center justify-between gap-2">
        <h2 id="launcher-h" className="font-display text-lg font-semibold">
          {t("home.tools")}
        </h2>
        <Button variant="ghost" size="sm" className="sm:hidden" aria-pressed={detail} onClick={() => setDetail((d) => !d)}>
          {t("home.showDetails")}
        </Button>
      </div>
      {isLoading && <p className="mt-3 text-sm text-muted">{t("common.loading")}</p>}
      <ul className={`mt-2 grid ${detail ? "grid-cols-1" : "grid-cols-2"} gap-2 sm:grid-cols-[repeat(auto-fill,minmax(15rem,1fr))]`}>
        {ordered.map((x) => (
          <li key={x.id} data-group={isKnownGroup(x.group) ? x.group : "none"}>
            <Link
              to={toolPath(x.id)}
              className="flex h-full items-start gap-2 rounded-xl border border-l-4 border-border border-l-g bg-surface px-2 py-2 shadow-card transition duration-200 hover:-translate-y-0.5 hover:border-g motion-reduce:transform-none sm:gap-3 sm:px-3 sm:py-2.5"
            >
              <ToolIcon toolId={x.id} group={x.group} className="max-sm:h-8 max-sm:w-8" />
              <span className="min-w-0">
                <span className="font-display block text-sm font-semibold leading-tight sm:text-base">
                  {t(`tools.${x.id}.title`, { defaultValue: x.title })}
                </span>
                <span className="mt-0.5 block text-xs font-medium text-g-ink">{t(`groups.${x.group}`, { defaultValue: x.group })}</span>
                <span className={`mt-0.5 line-clamp-2 block text-xs text-muted ${detail ? "" : "max-sm:hidden"}`}>
                  {t(`tools.${x.id}.description`, { defaultValue: x.description })}
                </span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
