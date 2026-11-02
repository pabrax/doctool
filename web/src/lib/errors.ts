import type { TFunction } from "i18next";
import { ApiError } from "./api";

/** Tools that work on a single picture (imagepdf is a PDF tool and keeps the document wording). */
export const IMAGE_TOOLS: readonly string[] = ["imageconvert", "imagecompress", "imageresize", "imagecrop", "imageclean"];

/** Image tools say "picture" and "crop area" where the PDF tools say "page". */
const IMAGE_STATE_KEY: Record<string, string> = {
  out_of_range: "out_of_image",
  too_large: "too_large_image",
  damaged: "damaged_image",
};

const humanize = (s: string) => s.replace(/[_-]+/g, " ").replace(/^./, (c) => c.toUpperCase());

/** Friendly, translated text for an API error; falls back to the server message. */
export function errorText(t: TFunction, err: unknown, toolId?: string, max?: number | null): string {
  const reason = reasonText(t, err, toolId, max);
  return err instanceof ApiError && err.file ? t("errors.in_file", { file: err.file, reason, interpolation: { escapeValue: false } }) : reason;
}

function reasonText(t: TFunction, err: unknown, toolId?: string, max?: number | null): string {
  if (err instanceof ApiError) {
    if (err.state === "invalid") {
      // FastAPI validation text is English: name the field instead of showing it raw.
      if (err.field) return t("errors.invalid_field", { field: t(`params.${err.field}`, { defaultValue: humanize(err.field) }) });
      return t("errors.invalid");
    }
    const state = err.state && toolId && IMAGE_TOOLS.includes(toolId) ? (IMAGE_STATE_KEY[err.state] ?? err.state) : err.state;
    const key = state ? `errors.${state}` : "";
    if (key) {
      const text = t(key, { defaultValue: "", max });
      if (text) return text;
    }
    return err.message || t("errors.generic");
  }
  return t("errors.generic");
}

export const isWrongPassword = (err: unknown) => err instanceof ApiError && err.state === "wrong_password";
