import { useTranslation } from "react-i18next";

/** Placeholder until T9 delivers the visual organizer. */
export function OrganizerPage() {
  const { t } = useTranslation();
  return (
    <div className="mx-auto max-w-5xl p-6">
      <h1 className="text-2xl font-semibold">{t("organizer.title")}</h1>
      <p className="mt-2 text-sm text-muted">{t("organizer.pickDocument")}</p>
    </div>
  );
}
