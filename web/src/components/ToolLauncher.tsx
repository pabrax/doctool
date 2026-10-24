import { ArrowUpRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { ToolIcon } from "@/components/ToolIcon";
import { isKnownGroup } from "@/lib/toolIcons";
import { GROUP_ORDER, toolPath, useTools } from "@/lib/useTools";

/** Home launcher: every tool as a tile, ordered by group, colored by group. */
export function ToolLauncher() {
  const { t } = useTranslation();
  const { data: tools, isLoading } = useTools();
  const ordered = [...(tools ?? [])].sort((a, b) => {
    const ia = GROUP_ORDER.indexOf(a.group as (typeof GROUP_ORDER)[number]);
    const ib = GROUP_ORDER.indexOf(b.group as (typeof GROUP_ORDER)[number]);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
  });

  return (
    <section aria-labelledby="launcher-h">
      <h2 id="launcher-h" className="font-display text-xl font-semibold">
        {t("home.tools")}
      </h2>
      {isLoading && <p className="mt-3 text-sm text-muted">{t("common.loading")}</p>}
      <ul className="mt-3 grid grid-cols-[repeat(auto-fill,minmax(15rem,1fr))] gap-3">
        {ordered.map((x) => (
          <li key={x.id} data-group={isKnownGroup(x.group) ? x.group : "none"}>
            <Link
              to={toolPath(x.id)}
              className="group/tile relative flex h-full flex-col gap-2 rounded-2xl border border-border border-t-[3px] border-t-g bg-surface p-4 shadow-card transition duration-200 hover:-translate-y-0.5 hover:border-g hover:border-t-g motion-reduce:transform-none"
            >
              <span className="flex items-center justify-between gap-2">
                <ToolIcon toolId={x.id} group={x.group} />
                <span className="text-xs font-medium text-g-ink">{t(`groups.${x.group}`, { defaultValue: x.group })}</span>
              </span>
              <span className="font-display text-lg font-semibold leading-snug">
                {t(`tools.${x.id}.title`, { defaultValue: x.title })}
              </span>
              <span className="line-clamp-2 text-sm text-muted">
                {t(`tools.${x.id}.description`, { defaultValue: x.description })}
              </span>
              <ArrowUpRight
                aria-hidden
                className="absolute bottom-3 right-3 h-4 w-4 text-g-ink opacity-0 transition-opacity group-hover/tile:opacity-100 group-focus-visible/tile:opacity-100"
              />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
