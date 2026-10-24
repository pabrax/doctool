import { Library, Menu, Monitor, Moon, Search, Sun } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet, Route, Routes } from "react-router-dom";
import { ToolIcon } from "@/components/ToolIcon";
import { LogoMark } from "@/components/Logo";
import { CommandPalette } from "@/components/CommandPalette";
import { setLanguage } from "@/i18n";
import { cn } from "@/lib/utils";
import { useTheme, type Theme } from "@/lib/theme";
import { GROUP_ORDER, toolPath, useTools } from "@/lib/useTools";
import { DocumentPage } from "@/pages/DocumentPage";
import { LibraryPage } from "@/pages/LibraryPage";
import { OrganizerPage } from "@/pages/OrganizerPage";
import { ToolPage } from "@/pages/ToolPage";

const navLink = ({ isActive }: { isActive: boolean }) =>
  cn(
    "relative flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors",
    isActive
      ? "bg-g-soft font-semibold text-g-ink before:absolute before:inset-y-1.5 before:left-0 before:w-1 before:rounded-full before:bg-g"
      : "text-text hover:bg-surface-2",
  );

function Sidebar({ onNavigate }: { onNavigate: () => void }) {
  const { t } = useTranslation();
  const { data: tools = [] } = useTools();
  return (
    <nav aria-label={t("nav.tools")} className="flex h-full flex-col gap-4 overflow-y-auto p-3">
      <NavLink to="/" end className={navLink} onClick={onNavigate}>
        <Library aria-hidden className="h-4 w-4" />
        {t("nav.home")}
      </NavLink>
      {GROUP_ORDER.map((group) => {
        const items = tools.filter((x) => x.group === group);
        if (!items.length) return null;
        return (
          <div key={group} data-group={group}>
            <h2 className="flex items-center gap-2 px-3 pb-1 text-sm font-semibold text-g-ink">
              <span aria-hidden className="h-2.5 w-2.5 rounded-[3px] bg-g" />
              {t(`groups.${group}`)}
            </h2>
            <ul>
              {items.map((x) => (
                <li key={x.id}>
                  <NavLink to={toolPath(x.id)} className={navLink} onClick={onNavigate}>
                    <ToolIcon toolId={x.id} group={x.group} variant="bare" />
                    {t(`tools.${x.id}.title`, { defaultValue: x.title })}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}

const themeIcon: Record<Theme, typeof Sun> = { system: Monitor, light: Sun, dark: Moon };
const nextTheme: Record<Theme, Theme> = { system: "light", light: "dark", dark: "system" };

function Shell() {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [theme, setTheme] = useTheme();
  const ThemeIcon = themeIcon[theme];
  const themeLabel = { system: t("nav.themeSystem"), light: t("nav.themeLight"), dark: t("nav.themeDark") }[theme];
  const lang = i18n.language.startsWith("es") ? "es" : "en";

  return (
    <div className="flex min-h-full flex-col md:flex-row">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-accent focus:px-3 focus:py-2 focus:text-accent-fg">
        {t("nav.skip")}
      </a>
      <aside
        className={cn(
          "w-full shrink-0 border-b border-border bg-surface md:sticky md:top-0 md:block md:h-screen md:w-64 md:border-b-0 md:border-r",
          open ? "block" : "hidden",
        )}
      >
        <div className="hidden items-center gap-2.5 px-4 py-4 md:flex">
          <LogoMark className="h-8 w-8" />
          <span className="font-display text-xl font-semibold">{t("app.name")}</span>
        </div>
        <Sidebar onNavigate={() => setOpen(false)} />
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-2 border-b border-border bg-surface px-3 py-2">
          <button
            type="button"
            aria-expanded={open}
            aria-label={t("nav.menu")}
            onClick={() => setOpen((v) => !v)}
            className="rounded-md p-2 hover:bg-surface-2 md:hidden"
          >
            <Menu aria-hidden className="h-5 w-5" />
          </button>
          <p className="font-display hidden text-base text-muted lg:block">{t("app.tagline")}</p>
          <button
            type="button"
            onClick={() => setPaletteOpen(true)}
            aria-keyshortcuts="Control+K"
            className="flex min-h-10 items-center gap-2 rounded-full border border-border bg-bg px-4 text-sm text-muted transition-colors hover:border-text/40 hover:bg-surface-2"
          >
            <Search aria-hidden className="h-4 w-4" />
            <span className="sr-only sm:not-sr-only">{t("nav.search")}</span>
            <kbd aria-hidden className="hidden rounded-md border border-border bg-surface px-1.5 text-xs sm:inline">Ctrl K</kbd>
          </button>
          <div className="ml-auto flex items-center gap-1">
            <label className="sr-only" htmlFor="lang">
              {t("nav.language")}
            </label>
            <select
              id="lang"
              className="min-h-9 rounded-md border border-border bg-surface px-2 text-sm"
              value={lang}
              onChange={(e) => setLanguage(e.target.value as "en" | "es")}
            >
              <option value="en">EN</option>
              <option value="es">ES</option>
            </select>
            <button
              type="button"
              onClick={() => setTheme(nextTheme[theme])}
              aria-label={`${t("nav.theme")}: ${themeLabel}`}
              title={`${t("nav.theme")}: ${themeLabel}`}
              className="inline-flex h-9 w-9 items-center justify-center rounded-md hover:bg-surface-2"
            >
              <ThemeIcon aria-hidden className="h-4 w-4" />
            </button>
          </div>
        </header>
        <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
        <main id="main" className="min-w-0 flex-1" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<LibraryPage />} />
        <Route path="library/:docId" element={<DocumentPage />} />
        <Route path="tools/:toolId" element={<ToolPage />} />
        <Route path="organize/:versionId?" element={<OrganizerPage />} />
      </Route>
    </Routes>
  );
}
