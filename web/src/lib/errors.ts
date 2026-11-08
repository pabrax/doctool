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

/** Office tools (LibreOffice lane, office uploads) speak of documents and sheets. */
export const OFFICE_TOOLS: readonly string[] = ["word2pdf", "excel2pdf", "ppt2pdf", "html2pdf", "pdf2word", "pdf2excel", "pdf2ppt"];

const OFFICE_STATE_KEY: Record<string, string> = {
  busy: "busy_office",
  unsupported: "unsupported_office",
  damaged: "damaged_office",
  too_large: "too_large_office",
  out_of_range: "out_of_range_office",
};

/** Error key for a server state, worded for the kind of tool that failed. */
function stateKey(state: string, toolId?: string): string {
  if (toolId && IMAGE_TOOLS.includes(toolId)) return IMAGE_STATE_KEY[state] ?? state;
  if (toolId && OFFICE_TOOLS.includes(toolId)) return OFFICE_STATE_KEY[state] ?? state;
  return state;
}

export const isBusy = (err: unknown) => err instanceof ApiError && err.state === "busy";

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
    const state = err.state ? stateKey(err.state, toolId) : err.state;
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
