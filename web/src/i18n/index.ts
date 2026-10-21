import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./en";
import es from "./es";

function initialLanguage(): "en" | "es" {
  try {
    const saved = localStorage.getItem("doctool.lang");
    if (saved === "en" || saved === "es") return saved;
  } catch {
    /* storage unavailable: fall through */
  }
  return navigator.language?.toLowerCase().startsWith("es") ? "es" : "en";
}

void i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, es: { translation: es } },
  lng: initialLanguage(),
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

export function setLanguage(lang: "en" | "es") {
  void i18n.changeLanguage(lang);
  document.documentElement.lang = lang;
  try {
    localStorage.setItem("doctool.lang", lang);
  } catch {
    /* ignore */
  }
}

export default i18n;
