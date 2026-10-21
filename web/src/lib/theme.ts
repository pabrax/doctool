import { useCallback, useState } from "react";

export type Theme = "system" | "light" | "dark";
const KEY = "doctool.theme";

export function readTheme(): Theme {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "light" || v === "dark") return v;
  } catch {
    /* storage unavailable */
  }
  return "system";
}

export function applyTheme(theme: Theme) {
  const root = document.documentElement;
  if (theme === "system") delete root.dataset.theme;
  else root.dataset.theme = theme;
  try {
    if (theme === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, theme);
  } catch {
    /* ignore */
  }
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(readTheme);
  const update = useCallback((next: Theme) => {
    applyTheme(next);
    setTheme(next);
  }, []);
  return [theme, update] as const;
}
