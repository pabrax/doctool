import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { axe } from "vitest-axe";
import "@/i18n";
import type { ParamsSchema } from "@/lib/types";
import { SchemaForm, defaultsFor, visibleFields } from "./SchemaForm";

const splitSchema: ParamsSchema = {
  properties: {
    mode: { type: "string", enum: ["ranges", "every", "extract"], default: "ranges", title: "Mode" },
    ranges: { type: "string", default: "", show_when: { mode: ["ranges", "extract"] } },
    every: { type: "integer", default: 1, minimum: 1, show_when: { mode: ["every"] } },
    merge_after: { type: "boolean", default: false, show_when: { mode: ["ranges"] } },
  },
};

function Harness({ schema, onValue }: { schema: ParamsSchema; onValue?: (v: Record<string, unknown>) => void }) {
  const [value, setValue] = useState(defaultsFor(schema));
  return (
    <SchemaForm
      toolId="split"
      schema={schema}
      value={value}
      onChange={(v) => {
        setValue(v);
        onValue?.(v);
      }}
    />
  );
}

describe("defaultsFor", () => {
  it("takes schema defaults and leaves optional nulls undefined", () => {
    const d = defaultsFor({
      properties: {
        a: { type: "integer", default: 3 },
        b: { anyOf: [{ type: "string" }, { type: "null" }], default: null },
      },
    });
    expect(d).toEqual({ a: 3 });
  });
});

describe("visibleFields", () => {
  it("hides fields whose show_when does not match", () => {
    expect(visibleFields(splitSchema, { mode: "ranges" })).toEqual(["mode", "ranges", "merge_after"]);
    expect(visibleFields(splitSchema, { mode: "every" })).toEqual(["mode", "every"]);
  });
});

describe("SchemaForm", () => {
  it("renders a select for enums, translated, and switches visible fields", async () => {
    render(<Harness schema={splitSchema} />);
    expect(screen.getByRole("combobox", { name: /mode/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/pages$/i)).toBeInTheDocument(); // ranges
    expect(screen.queryByLabelText(/pages per file/i)).not.toBeInTheDocument();
    await userEvent.selectOptions(screen.getByRole("combobox", { name: /mode/i }), "every");
    expect(screen.getByLabelText(/pages per file/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/^pages$/i)).not.toBeInTheDocument();
  });

  it("emits numbers for integer inputs and booleans for checkboxes", async () => {
    const seen: Record<string, unknown>[] = [];
    render(<Harness schema={splitSchema} onValue={(v) => seen.push(v)} />);
    await userEvent.click(screen.getByRole("checkbox"));
    expect(seen.at(-1)).toMatchObject({ merge_after: true });
    await userEvent.selectOptions(screen.getByRole("combobox"), "every");
    const n = screen.getByRole("spinbutton");
    fireEvent.change(n, { target: { value: "5" } });
    expect(seen.at(-1)).toMatchObject({ every: 5 });
  });

  it("masks secret fields as password inputs", () => {
    render(
      <SchemaForm
        toolId="protect"
        schema={{ properties: { password: { type: "string", minLength: 1, secret: true } }, required: ["password"] }}
        value={{}}
        onChange={() => {}}
      />,
    );
    const input = screen.getByLabelText(/password/i);
    expect(input).toHaveAttribute("type", "password");
    expect(input).toBeRequired();
    expect(input).toHaveAttribute("autocomplete", "new-password");
  });

  it("uses a color input for hex color patterns and number bounds for ranges", () => {
    render(
      <SchemaForm
        toolId="watermark"
        schema={{
          properties: {
            color: { type: "string", pattern: "^#[0-9a-fA-F]{6}$", default: "#808080" },
            opacity: { type: "number", exclusiveMinimum: 0, maximum: 1, default: 0.3 },
          },
        }}
        value={{ color: "#808080", opacity: 0.3 }}
        onChange={() => {}}
      />,
    );
    expect(screen.getByLabelText(/color/i)).toHaveAttribute("type", "color");
    const op = screen.getByLabelText(/opacity/i);
    expect(op).toHaveAttribute("max", "1");
    expect(op).toHaveAttribute("step", "any");
  });

  it("falls back to a JSON textarea for arrays and flags invalid JSON", async () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        toolId="x"
        schema={{ properties: { order: { type: "array" } } }}
        value={{}}
        onChange={onChange}
      />,
    );
    const area = screen.getByRole("textbox");
    fireEvent.change(area, { target: { value: "[1,2" } });
    expect(area).toHaveAttribute("aria-invalid", "true");
    fireEvent.change(area, { target: { value: "[1,2]" } });
    expect(onChange).toHaveBeenLastCalledWith({ order: [1, 2] });
  });

  it("has no detectable accessibility violations", async () => {
    const { container } = render(<Harness schema={splitSchema} />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
