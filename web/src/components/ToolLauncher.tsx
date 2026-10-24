import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { ToolIcon } from "@/components/ToolIcon";
import { isKnownGroup } from "@/lib/toolIcons";
import { sortByGroup, toolPath, useTools } from "@/lib/useTools";

/** Home launcher: every tool as a tile, ordered by group, colored by group. */
export function ToolLauncher() {
  const { t } = useTranslation();
  const { data: tools, isLoading } = useTools();
  const ordered = sortByGroup(tools ?? []);

  return (
    <section aria-labelledby="launcher-h">
      <h2 id="launcher-h" className="font-display text-lg font-semibold">
        {t("home.tools")}
      </h2>
      {isLoading && <p className="mt-3 text-sm text-muted">{t("common.loading")}</p>}
      <ul className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-[repeat(auto-fill,minmax(12.5rem,1fr))]">
        {ordered.map((x) => (
          <li key={x.id} data-group={isKnownGroup(x.group) ? x.group : "none"}>
            <Link
              to={toolPath(x.id)}
              title={t(`tools.${x.id}.description`, { defaultValue: x.description })}
              className="flex h-full items-center gap-2 rounded-xl border border-l-4 sm:gap-3 border-border border-l-g bg-surface px-2 py-2 shadow-card sm:px-3 transition duration-200 hover:-translate-y-0.5 hover:border-g motion-reduce:transform-none"
            >
              <ToolIcon toolId={x.id} group={x.group} className="max-sm:hidden" />
              <span className="min-w-0">
                <span className="font-display block text-sm leading-tight sm:truncate sm:text-base font-semibold leading-tight">
                  {t(`tools.${x.id}.title`, { defaultValue: x.title })}
                </span>
                <span className="block text-xs font-medium text-g-ink max-sm:hidden">{t(`groups.${x.group}`, { defaultValue: x.group })}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
