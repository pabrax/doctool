import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import type { JsonSchemaProp, ParamsSchema } from "@/lib/types";
import { hintClass, inputClass, labelClass } from "./ui";

export type FormValue = Record<string, unknown>;

/** Merge `anyOf: [X, null]` (Pydantic's Optional) into X, keeping the outer metadata. */
function resolve(prop: JsonSchemaProp): JsonSchemaProp {
  if (!prop.anyOf) return prop;
  const inner = prop.anyOf.find((p) => p.type !== "null") ?? {};
  return { ...inner, ...prop, anyOf: undefined, type: inner.type ?? prop.type };
}

export function defaultsFor(schema: ParamsSchema): FormValue {
  const out: FormValue = {};
  for (const [name, raw] of Object.entries(schema.properties ?? {})) {
    if (raw.default !== undefined && raw.default !== null) out[name] = raw.default;
  }
  return out;
}

export function visibleFields(schema: ParamsSchema, value: FormValue): string[] {
  return Object.entries(schema.properties ?? {})
    .filter(([, raw]) => {
      const when = resolve(raw).show_when;
      if (!when) return true;
      return Object.entries(when).every(([dep, allowed]) => allowed.includes(value[dep] as string));
    })
    .map(([name]) => name);
}

const humanize = (s: string) => s.replace(/[_-]+/g, " ").replace(/^./, (c) => c.toUpperCase());

interface Props {
  toolId: string;
  schema: ParamsSchema;
  value: FormValue;
  onChange: (next: FormValue) => void;
  /** Field names to leave out (a dedicated UI handles them). */
  hide?: string[];
}

export function SchemaForm({ toolId, schema, value, onChange, hide = [] }: Props) {
  const { t } = useTranslation();
  const baseId = useId();
  const set = (name: string, next: unknown) => {
    const copy = { ...value };
    if (next === undefined) delete copy[name];
    else copy[name] = next;
    onChange(copy);
  };

  const fields = visibleFields(schema, value).filter((n) => !hide.includes(n));
  return (
    <div className="grid gap-4">
      {fields.map((name) => {
        const prop = resolve(schema.properties![name]);
        const id = `${baseId}-${toolId}-${name}`;
        const hintId = `${id}-hint`;
        const label = t(`params.${name}`, { defaultValue: humanize(name) });
        const required = schema.required?.includes(name) ?? false;
        const hint = prop.description;
        const common = { id, "aria-describedby": hint ? hintId : undefined };

        let control: React.ReactNode;
        if (prop.type === "boolean") {
          return (
            <div key={name}>
              <label className="flex items-center gap-2 text-sm text-text" htmlFor={id}>
                <input
                  {...common}
                  type="checkbox"
                  className="h-4 w-4 accent-[var(--accent)]"
                  checked={Boolean(value[name])}
                  onChange={(e) => set(name, e.target.checked)}
                />
                {label}
              </label>
              {hint && (
                <p id={hintId} className={hintClass}>
                  {hint}
                </p>
              )}
            </div>
          );
        }
        if (prop.enum) {
          control = (
            <select
              {...common}
              className={inputClass}
              value={String(value[name] ?? prop.default ?? "")}
              onChange={(e) => {
                const raw = e.target.value;
                set(name, typeof prop.enum![0] === "number" ? Number(raw) : raw);
              }}
            >
              {prop.enum.map((v) => (
                <option key={String(v)} value={String(v)}>
                  {typeof v === "number"
                    ? `${v}°`
                    : t(`values.${v}`, { defaultValue: humanize(String(v)) })}
                </option>
              ))}
            </select>
          );
        } else if (prop.type === "integer" || prop.type === "number") {
          control = (
            <input
              {...common}
              type="number"
              className={inputClass}
              min={prop.minimum ?? prop.exclusiveMinimum}
              max={prop.maximum ?? prop.exclusiveMaximum}
              step={prop.type === "integer" ? 1 : "any"}
              required={required}
              value={(value[name] as number | undefined) ?? ""}
              onChange={(e) => set(name, e.target.value === "" ? undefined : Number(e.target.value))}
            />
          );
        } else if (prop.type === "string") {
          const isColor = prop.pattern?.includes("#") && prop.pattern.includes("{6}");
          control = (
            <input
              {...common}
              type={prop.secret ? "password" : isColor ? "color" : "text"}
              autoComplete={prop.secret ? "new-password" : "off"}
              className={isColor ? "h-9 w-16 cursor-pointer rounded-md border border-border bg-surface p-1" : inputClass}
              required={required || (prop.minLength ?? 0) > 0}
              value={String(value[name] ?? "")}
              onChange={(e) => set(name, e.target.value)}
            />
          );
        } else {
          control = <JsonField {...common} value={value[name]} onValid={(v) => set(name, v)} />;
        }
        return (
          <div key={name}>
            <label htmlFor={id} className={labelClass}>
              {label}
              {required ? <span aria-hidden="true"> *</span> : null}
            </label>
            {control}
            {hint && (
              <p id={hintId} className={hintClass}>
                {hint}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}

function JsonField({
  value,
  onValid,
  ...rest
}: {
  id: string;
  "aria-describedby"?: string;
  value: unknown;
  onValid: (v: unknown) => void;
}) {
  const [text, setText] = useState(value === undefined ? "" : JSON.stringify(value));
  const [invalid, setInvalid] = useState(false);
  return (
    <textarea
      {...rest}
      rows={3}
      spellCheck={false}
      className={`${inputClass} font-mono`}
      aria-invalid={invalid}
      value={text}
      onChange={(e) => {
        setText(e.target.value);
        if (e.target.value.trim() === "") {
          setInvalid(false);
          onValid(undefined);
          return;
        }
        try {
          onValid(JSON.parse(e.target.value));
          setInvalid(false);
        } catch {
          setInvalid(true);
        }
      }}
    />
  );
}
