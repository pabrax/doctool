import { ApiError, api } from "./api";
import { errorText } from "./errors";
import i18n from "@/i18n";
import en from "@/i18n/en";
import es from "@/i18n/es";
import { formatBytes } from "./utils";

function keys(obj: Record<string, unknown>, prefix = ""): string[] {
  return Object.entries(obj).flatMap(([k, v]) =>
    v && typeof v === "object" ? keys(v as Record<string, unknown>, `${prefix}${k}.`) : [`${prefix}${k}`],
  );
}

describe("i18n", () => {
  it("English and Spanish dictionaries have exactly the same keys", () => {
    expect(keys(es as unknown as Record<string, unknown>).sort()).toEqual(keys(en as unknown as Record<string, unknown>).sort());
  });

  it("has no empty strings", () => {
    for (const dict of [en, es]) for (const k of keys(dict as unknown as Record<string, unknown>)) expect(k).toBeTruthy();
    const empties = keys(en as unknown as Record<string, unknown>).filter((k) => !k.split(".").reduce((o: any, p) => o?.[p], en));
    expect(empties).toEqual([]);
  });
});

describe("api client", () => {
  const respond = (status: number, body: unknown) =>
    (globalThis.fetch = vi.fn(async () => new Response(JSON.stringify(body), { status })) as typeof fetch);

  it("maps a documented processing error to a state", async () => {
    respond(400, { detail: { type: "ProcessingError", state: "wrong_password", message: "pw" } });
    await expect(api.documents()).rejects.toMatchObject({ status: 400, state: "wrong_password", message: "pw" });
  });

  it("flattens validation errors with their field path", async () => {
    respond(422, { detail: [{ loc: ["ranges"], msg: "required" }] });
    await expect(api.documents()).rejects.toMatchObject({ state: "invalid", message: "ranges: required" });
  });

  it("handles plain string details and network failures", async () => {
    respond(404, { detail: "document not found" });
    await expect(api.document("x")).rejects.toMatchObject({ status: 404, message: "document not found" });
    globalThis.fetch = vi.fn(async () => {
      throw new TypeError("fail");
    }) as typeof fetch;
    await expect(api.documents()).rejects.toMatchObject({ state: "network" });
  });

  it("returns undefined for 204", async () => {
    globalThis.fetch = vi.fn(async () => new Response(null, { status: 204 })) as typeof fetch;
    await expect(api.deleteDocument("x")).resolves.toBeUndefined();
  });

  it("builds URLs the backend serves", () => {
    expect(api.versionDownloadUrl("v", true)).toBe("/api/v1/versions/v/download?inline=1");
    expect(api.thumbnailUrl("v", 2, 100)).toBe("/api/v1/versions/v/thumbnail/2?width=100");
    expect(api.taskDownloadUrl("t")).toBe("/api/v1/tasks/t/download");
  });
});

describe("errorText", () => {
  it("translates known states and falls back to the server message", async () => {
    await i18n.changeLanguage("en");
    const t = i18n.t.bind(i18n);
    expect(errorText(t, new ApiError(400, "x", "damaged"))).toMatch(/damaged/i);
    expect(errorText(t, new ApiError(500, "boom"))).toBe("boom");
    expect(errorText(t, new Error("x"))).toBe(en.errors.generic);
  });

  it("uses generic copy for unsupported and image-specific copy for image tools", async () => {
    await i18n.changeLanguage("en");
    const t = i18n.t.bind(i18n);
    expect(errorText(t, new ApiError(400, "x", "unsupported"))).toBe(en.errors.unsupported);
    expect(errorText(t, new ApiError(400, "x", "out_of_range"))).toBe(en.errors.out_of_range);
    expect(errorText(t, new ApiError(400, "x", "out_of_range"), "imagecrop")).toBe(en.errors.out_of_image);
    expect(errorText(t, new ApiError(400, "x", "too_large"), "imageresize")).toBe(en.errors.too_large_image);
    expect(errorText(t, new ApiError(400, "x", "out_of_range"), "split")).toBe(en.errors.out_of_range);
    expect(errorText(t, new ApiError(400, "x", "out_of_range"), "imagepdf")).toBe(en.errors.out_of_range);
    await i18n.changeLanguage("es");
    expect(errorText(i18n.t.bind(i18n), new ApiError(400, "x", "unsupported"))).toMatch(/no se puede procesar/);
    await i18n.changeLanguage("en");
  });

  it("home title no longer says PDFs only", () => {
    expect(en.home.title).toBe("What shall we do with your files?");
    expect(es.home.title).toBe("¿Qué hacemos con tus archivos?");
  });

  it("neutral quality label and image values exist in both languages", () => {
    expect(en.params.quality).toBe("Quality");
    expect(es.params.quality).toBe("Calidad");
    for (const dict of [en, es]) {
      for (const v of ["fit_box", "exact", "percent", "web", "email", "max", "ratio", "box", "1-1", "4-3", "3-2", "16-9", "webp", "avif"])
        expect((dict.values as Record<string, string>)[v]).toBeTruthy();
      for (const p of ["preset", "width", "height", "percent", "ratio", "x", "y", "background", "keep_metadata"])
        expect((dict.params as Record<string, string>)[p]).toBeTruthy();
      expect(dict.toolPage.imageKept).toContain("{{after}}");
      expect(dict.toolPage.larger).toContain("{{pct}}");
      expect(dict.errors).not.toHaveProperty("animated");
      expect(dict.errors).toHaveProperty("unsupported");
      expect(dict.errors).toHaveProperty("not_image");
      expect(dict.dropzone.rejectedImage).toBeTruthy();
    }
  });
});

describe("formatBytes", () => {
  it.each([
    [512, "512 B"],
    [2048, "2.0 KB"],
    [5 * 1024 * 1024, "5.0 MB"],
    [300 * 1024, "300 KB"],
  ])("%i -> %s", (n, s) => expect(formatBytes(n)).toBe(s));
});

describe("image error and hint copy (QA1-web)", () => {
  const imageErr = async (lang: "en" | "es", state: string, tool: string, status = 422) => {
    await i18n.changeLanguage(lang);
    return errorText(i18n.t.bind(i18n), new ApiError(status, "raw english", state), tool);
  };
  afterEach(() => i18n.changeLanguage("en"));

  it("maps upload and processing states for image tools", async () => {
    expect(await imageErr("en", "not_image", "imageconvert")).toBe(en.errors.not_image);
    expect(await imageErr("en", "damaged", "imagecompress")).toBe("This picture looks damaged or incomplete. Try another copy.");
    expect(await imageErr("es", "damaged", "imagecompress")).toBe("Esta imagen parece dañada o incompleta. Prueba con otra copia.");
    expect(await imageErr("en", "damaged", "split")).toBe(en.errors.damaged);
    expect(await imageErr("es", "too_large", "imageresize", 413)).toBe(es.errors.too_large_image);
    expect(await imageErr("es", "unsupported", "imageclean")).toBe(es.errors.unsupported);
    expect(await imageErr("es", "out_of_range", "imagecrop")).toBe(es.errors.out_of_image);
  });

  it("413 without a state still shows translated text, for every tool", async () => {
    globalThis.fetch = vi.fn(async () => new Response(JSON.stringify({ detail: "file too large" }), { status: 413 })) as typeof fetch;
    const err = await api.documents().catch((e) => e);
    await i18n.changeLanguage("es");
    expect(errorText(i18n.t.bind(i18n), err, "merge")).toBe(es.errors.too_large);
    expect(errorText(i18n.t.bind(i18n), err, "imageresize")).toBe(es.errors.too_large_image);
  });

  it("422 validation lists name the field label instead of the raw message", async () => {
    globalThis.fetch = vi.fn(
      async () => new Response(JSON.stringify({ detail: [{ loc: ["body", "params", "quality"], msg: "Input should be less than or equal to 100" }] }), { status: 422 }),
    ) as typeof fetch;
    const err = await api.documents().catch((e) => e);
    await i18n.changeLanguage("en");
    expect(errorText(i18n.t.bind(i18n), err, "imageconvert")).toBe('Check the value of "Quality".');
    await i18n.changeLanguage("es");
    expect(errorText(i18n.t.bind(i18n), err, "imageconvert")).toBe("Revisa el valor de «Calidad».");
    expect(errorText(i18n.t.bind(i18n), err, "imageconvert")).not.toMatch(/Input should/);
  });

  it("422 without a usable field falls back to the generic invalid text", async () => {
    await i18n.changeLanguage("en");
    expect(errorText(i18n.t.bind(i18n), new ApiError(422, "params: Value error", "invalid"), "imageresize")).toBe(en.errors.invalid);
  });

  it("every image-tool field with a description has a hint in both languages", () => {
    const fields: Record<string, string[]> = {
      imageconvert: ["format", "quality", "background", "keep_metadata"],
      imagecompress: ["preset"],
      imageresize: ["mode", "width", "height", "percent"],
      imagecrop: ["mode", "ratio", "x", "y", "width", "height"],
    };
    for (const dict of [en, es])
      for (const [tool, names] of Object.entries(fields))
        for (const n of names) expect(((dict.hints as any)[tool] ?? {})[n], `${tool}.${n}`).toBeTruthy();
    expect(en.hints.imageresize.mode).toMatch(/proportions/);
  });
});
