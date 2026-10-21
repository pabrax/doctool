import { FileText, Library, Menu, Monitor, Moon, Sun } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { NavLink, Outlet, Route, Routes } from "react-router-dom";
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
    "flex items-center gap-2 rounded-md px-3 py-2 text-sm",
    isActive ? "bg-accent-soft font-medium text-accent" : "text-text hover:bg-surface-2",
  );

function Sidebar({ onNavigate }: { onNavigate: () => void }) {
  const { t } = useTranslation();
  const { data: tools = [] } = useTools();
  return (
    <nav aria-label={t("nav.tools")} className="flex h-full flex-col gap-4 overflow-y-auto p-3">
      <NavLink to="/" end className={navLink} onClick={onNavigate}>
        <Library aria-hidden className="h-4 w-4" />
        {t("nav.library")}
      </NavLink>
      {GROUP_ORDER.map((group) => {
        const items = tools.filter((x) => x.group === group);
        if (!items.length) return null;
        return (
          <div key={group}>
            <h2 className="px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-muted">{t(`groups.${group}`)}</h2>
            <ul>
              {items.map((x) => (
                <li key={x.id}>
                  <NavLink to={toolPath(x.id)} className={navLink} onClick={onNavigate}>
                    <FileText aria-hidden className="h-4 w-4 shrink-0" />
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
        <div className="hidden items-center gap-2 px-4 py-4 md:flex">
          <div aria-hidden className="grid h-7 w-7 place-items-center rounded-md bg-accent text-accent-fg">
            <FileText className="h-4 w-4" />
          </div>
          <span className="text-base font-semibold">{t("app.name")}</span>
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
          <p className="hidden text-sm text-muted sm:block">{t("app.tagline")}</p>
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
