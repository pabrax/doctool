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
});

describe("formatBytes", () => {
  it.each([
    [512, "512 B"],
    [2048, "2.0 KB"],
    [5 * 1024 * 1024, "5.0 MB"],
    [300 * 1024, "300 KB"],
  ])("%i -> %s", (n, s) => expect(formatBytes(n)).toBe(s));
});
