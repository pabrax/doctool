import type { TFunction } from "i18next";
import { ApiError } from "./api";

/** Friendly, translated text for an API error; falls back to the server message. */
export function errorText(t: TFunction, err: unknown): string {
  if (err instanceof ApiError) {
    const key = err.state ? `errors.${err.state}` : "";
    if (key) {
      const text = t(key, { defaultValue: "" });
      if (text) return err.state === "invalid" ? `${text} ${err.message}` : text;
    }
    return err.message || t("errors.generic");
  }
  return t("errors.generic");
}

export const isWrongPassword = (err: unknown) => err instanceof ApiError && err.state === "wrong_password";
