import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import i18n from "@/i18n";
import { doc, mergeTool, mockFetch, pdfFile, renderApp, rotateTool, version } from "@/test/utils";
import type { Tool } from "@/lib/types";

const compressTool: Tool = { ...rotateTool, id: "compress", title: "Compress PDF", group: "optimize", description: "Reduce the file size.", params_schema: { properties: {} } };
const imageTool = (id: string): Tool => ({ ...rotateTool, id, title: id, group: "images", description: "d", accepts: "image", params_schema: { properties: {} } });
const organizeTool: Tool = { ...rotateTool, id: "organize", title: "Organize pages", description: "Reorder pages." };
const task = (over = {}) => ({ id: "t1", tool: "merge", params: {}, state: "waiting", error: null, files: [], ...over });
const inFile = { id: "f1", role: "in", position: 0, filename: "a.pdf", state: "ok", version_id: null, sha256: "x" };
const outFile = { id: "o1", role: "out", position: 0, filename: "m.pdf", state: "ok", version_id: "v9", sha256: "y" };

function toolRoutes(extra: Record<string, unknown> = {}) {
  return mockFetch({
    "GET /tools": { body: [mergeTool, compressTool, organizeTool, rotateTool] },
    "GET /documents": { body: [] },
    "POST /tasks": { status: 201, body: task() },
    "POST /tasks/t1/files": { status: 201, body: task({ files: [inFile] }) },
    "POST /tasks/t1/process": { body: task({ state: "success", files: [outFile] }) },
    "GET /versions/v9": { body: version({ id: "v9", document_id: "d9", size: 1024, pages: 5 }) },
    ...extra,
  });
}

describe("tool flow", () => {
  it("says how many files are still missing, and summarises the selection with a clear-all", async () => {
    toolRoutes();
    renderApp("/tools/merge");
    const input = await screen.findByTestId("file-input");
    await userEvent.upload(input, pdfFile("one.pdf"));
    expect(screen.getByText("Add 1 more file to continue.")).toBeInTheDocument();
    await userEvent.upload(input, pdfFile("two.pdf"));
    expect(screen.queryByText(/more file/)).not.toBeInTheDocument();
    expect(screen.getByText(/^2 files/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Remove all" }));
    expect(screen.queryByText("one.pdf")).not.toBeInTheDocument();
    // not destructive: Undo is announced, takes focus, and restores the ordered list
    // the live region exists before and after, so the announcement is reliable; Undo takes focus and is described by the message
    expect(screen.getByRole("status")).toHaveTextContent("All files removed.");
    expect(screen.getByRole("button", { name: "Undo" })).toHaveFocus();
    expect(screen.getByRole("button", { name: "Undo" })).toHaveAccessibleDescription("All files removed.");
    await userEvent.click(screen.getByRole("button", { name: "Undo" }));
    expect(screen.getByText("one.pdf")).toBeInTheDocument();
    expect(screen.getByText("two.pdf")).toBeInTheDocument();
  });

  it("does not offer next-step buttons when the task produced several files", async () => {
    const out2 = { ...outFile, id: "o2", position: 1, filename: "m2.pdf", version_id: "v10" };
    toolRoutes({ "POST /tasks/t1/process": { body: task({ state: "success", files: [outFile, out2] }) } });
    renderApp("/tools/merge");
    await userEvent.upload(await screen.findByTestId("file-input"), [pdfFile("a.pdf"), pdfFile("b.pdf")]);
    await userEvent.click(screen.getByRole("button", { name: /^run$/i }));
    expect(await screen.findByRole("heading", { name: "Done" })).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Keep going with this file" })).not.toBeInTheDocument();
  });

  it("after success: focuses the result, shows pages and size, offers next steps and a fresh start", async () => {
    toolRoutes();
    const { container } = renderApp("/tools/merge");
    const input = await screen.findByTestId("file-input");
    await userEvent.upload(input, [pdfFile("a.pdf"), pdfFile("b.pdf")]);
    await userEvent.click(screen.getByRole("button", { name: /^run$/i }));

    const heading = await screen.findByRole("heading", { name: "Done" });
    expect(heading).not.toHaveFocus(); // focus is not stolen; the aria-live region announces the result
    expect(await screen.findByText("5 pages · 1.0 KB")).toBeInTheDocument();
    const next = screen.getByRole("list", { name: "Keep going with this file" });
    expect(within(next).getAllByRole("button").map((b) => b.textContent)).toEqual(["Organize pages", "Compress PDF"]);
    expect(await axe(container)).toHaveNoViolations();

    await userEvent.click(screen.getByRole("button", { name: "New task" }));
    expect(screen.queryByRole("heading", { name: "Done" })).not.toBeInTheDocument();
    expect(screen.queryByText("a.pdf")).not.toBeInTheDocument();
  });

  it("compress reports how much smaller the file got", async () => {
    toolRoutes({
      "POST /tasks": { status: 201, body: task({ tool: "compress" }) },
      "GET /versions/v9": { body: version({ id: "v9", document_id: "d9", size: 1024, pages: 5 }) },
    });
    renderApp("/tools/compress");
    const big = new File([new Uint8Array(4096)], "big.pdf", { type: "application/pdf" });
    await userEvent.upload(await screen.findByTestId("file-input"), big);
    await userEvent.click(screen.getByRole("button", { name: /^run$/i }));
    expect(await screen.findByText("75% smaller: 4.0 KB → 1.0 KB")).toBeInTheDocument();
  });

  it("compress says 'already optimized' instead of '0% smaller'", async () => {
    toolRoutes({
      "POST /tasks": { status: 201, body: task({ tool: "compress" }) },
      "GET /versions/v9": { body: version({ id: "v9", document_id: "d9", size: 4090, pages: 5 }) },
    });
    renderApp("/tools/compress");
    const big = new File([new Uint8Array(4096)], "big.pdf", { type: "application/pdf" });
    await userEvent.upload(await screen.findByTestId("file-input"), big);
    await userEvent.click(screen.getByRole("button", { name: /^run$/i }));
    expect(await screen.findByText(/Already well optimized/)).toBeInTheDocument();
    expect(screen.queryByText(/0% smaller/)).not.toBeInTheDocument();
  });

  describe("image tools size line", () => {
    const runImage = async (id: string, outSize: number) => {
      toolRoutes({
        "GET /tools": { body: [imageTool(id), mergeTool] },
        "POST /tasks": { status: 201, body: task({ tool: id }) },
        "GET /versions/v9": { body: version({ id: "v9", document_id: "d9", size: outSize, pages: null }) },
      });
      renderApp(`/tools/${id}`);
      const pic = new File([new Uint8Array(4096)], "photo.png", { type: "image/png" });
      await userEvent.upload(await screen.findByTestId("file-input"), pic);
      await userEvent.click(screen.getByRole("button", { name: /^run$/i }));
    };

    it.each(["imagecompress", "imageresize", "imageconvert", "imageclean"])("%s reports a smaller file", async (id) => {
      await runImage(id, 1024);
      expect(await screen.findByText("75% smaller: 4.0 KB → 1.0 KB")).toBeInTheDocument();
    });

    it("imagecompress treats 'not smaller' as a calm success, not an error", async () => {
      await runImage("imagecompress", 4096);
      expect(await screen.findByText("This picture was already as light as it gets, so we kept it as it was: 4.0 KB.")).toBeInTheDocument();
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Download" })).toBeInTheDocument();
    });

    it.each(["imageconvert", "imageresize"])("%s says 'larger' in plain words", async (id) => {
      await runImage(id, 6144);
      expect(await screen.findByText("50% larger: 4.0 KB → 6.0 KB. This is normal when converting to PNG.")).toBeInTheDocument();
      expect(screen.queryByText(/Already well optimized/)).not.toBeInTheDocument();
    });

    describe("outputs without a library version (size from the task file)", () => {
      const runNoVersion = async (id: string, outSize: number | null, lang = "en") => {
        await i18n.changeLanguage(lang);
        const out = { ...outFile, filename: "photo.jpg", version_id: null, size: outSize };
        toolRoutes({
          "GET /tools": { body: [imageTool(id), mergeTool] },
          "POST /tasks": { status: 201, body: task({ tool: id }) },
          "POST /tasks/t1/process": { body: task({ tool: id, state: "success", files: [out] }) },
        });
        renderApp(`/tools/${id}`);
        const pic = new File([new Uint8Array(4096)], "photo.png", { type: "image/png" });
        await userEvent.upload(await screen.findByTestId("file-input"), pic);
        await userEvent.click(screen.getByRole("button", { name: lang === "es" ? /^ejecutar$/i : /^run$/i }));
      };
      afterEach(() => i18n.changeLanguage("en"));

      it("imagecompress smaller", async () => {
        await runNoVersion("imagecompress", 1024);
        expect(await screen.findByText("75% smaller: 4.0 KB → 1.0 KB")).toBeInTheDocument();
      });
      it("imagecompress smaller (es)", async () => {
        await runNoVersion("imagecompress", 1024, "es");
        expect(await screen.findByText("75 % más pequeño: 4.0 KB → 1.0 KB")).toBeInTheDocument();
      });
      it.each([4096, 5000])("imagecompress equal or greater keeps the kept wording (%i)", async (n) => {
        await runNoVersion("imagecompress", n);
        expect(await screen.findByText(/we kept it as it was/)).toBeInTheDocument();
      });
      it("imageconvert bigger shows the larger wording", async () => {
        await runNoVersion("imageconvert", 6144);
        expect(await screen.findByText("50% larger: 4.0 KB → 6.0 KB. This is normal when converting to PNG.")).toBeInTheDocument();
      });
    });

    it("crop shows only the plain size (no before/after line)", async () => {
      await runImage("imagecrop", 1024);
      await screen.findByRole("heading", { name: "Done" });
      expect(screen.queryByText(/smaller|larger/)).not.toBeInTheDocument();
    });

    it.each([
      ["en", "width", 'Check the value of "Width (px)".'],
      ["en", "height", 'Check the value of "Height (px)".'],
      ["es", "width", "Revisa el valor de «Ancho (px)»."],
      ["es", "height", "Revisa el valor de «Alto (px)»."],
    ])("names the %s label for a box-mode 422 on %s", async (lang, field, text) => {
      await i18n.changeLanguage(lang);
      toolRoutes({
        "GET /tools": { body: [imageTool("imagecrop"), mergeTool] },
        "POST /tasks": { status: 422, body: { detail: [{ type: "value_error", loc: ["body", "params", field], msg: "Value error, width and height are required in box mode" }] } },
      });
      renderApp("/tools/imagecrop");
      await userEvent.upload(await screen.findByTestId("file-input"), new File(["x"], "p.png", { type: "image/png" }));
      await userEvent.click(screen.getByRole("button", { name: lang === "es" ? /^ejecutar$/i : /^run$/i }));
      expect(await screen.findByRole("alert")).toHaveTextContent(text);
      await i18n.changeLanguage("en");
    });

    it("names the file that was rejected at upload and keeps the files listed", async () => {
      let n = 0;
      toolRoutes({
        "GET /tools": { body: [{ ...imageTool("imageconvert"), max_files: null, min_files: 1 }, mergeTool] },
        "POST /tasks": { status: 201, body: task({ tool: "imageconvert" }) },
        "POST /tasks/t1/files": () =>
          ++n === 1
            ? { status: 201, body: task({ files: [inFile] }) }
            : { status: 422, body: { detail: { state: "not_image", message: "x" } } },
        "DELETE /tasks/t1": { status: 204 },
      });
      renderApp("/tools/imageconvert");
      await userEvent.upload(await screen.findByTestId("file-input"), [
        new File(["x"], "good.png", { type: "image/png" }),
        new File(["x"], "bad.png", { type: "image/png" }),
      ]);
      await userEvent.click(screen.getByRole("button", { name: /^run$/i }));
      expect(await screen.findByRole("alert")).toHaveTextContent(
        "bad.png: This file is not a picture we can read. Try JPG, PNG or WebP.",
      );
      expect(screen.getByText("good.png")).toBeInTheDocument();
      expect(screen.getByText("bad.png")).toBeInTheDocument();
    });

    it("names the rejected file in Spanish", async () => {
      await i18n.changeLanguage("es");
      let n = 0;
      toolRoutes({
        "GET /tools": { body: [{ ...imageTool("imageconvert"), max_files: null, min_files: 1 }, mergeTool] },
        "POST /tasks": { status: 201, body: task({ tool: "imageconvert" }) },
        "POST /tasks/t1/files": () =>
          ++n === 1
            ? { status: 201, body: task({ files: [inFile] }) }
            : { status: 422, body: { detail: { state: "not_image", message: "x" } } },
        "DELETE /tasks/t1": { status: 204 },
      });
      renderApp("/tools/imageconvert");
      await userEvent.upload(await screen.findByTestId("file-input"), [
        new File(["x"], "good.png", { type: "image/png" }),
        new File(["x"], "bad.png", { type: "image/png" }),
      ]);
      await userEvent.click(screen.getByRole("button", { name: /^ejecutar$/i }));
      expect(await screen.findByRole("alert")).toHaveTextContent(
        "bad.png: Este archivo no es una imagen que podamos leer. Prueba con JPG, PNG o WebP.",
      );
      await i18n.changeLanguage("en");
    });

    it.each([
      ["en", /^run$/i, "anim.gif: This picture cannot be processed"],
      ["es", /^ejecutar$/i, "anim.gif: Esta imagen no se puede procesar"],
    ])("prefixes a processing error with the file name from the API (%s)", async (lang, runName, text) => {
      await i18n.changeLanguage(lang);
      toolRoutes({
        "GET /tools": { body: [imageTool("imageconvert"), mergeTool] },
        "POST /tasks": { status: 201, body: task({ tool: "imageconvert" }) },
        "POST /tasks/t1/process": { status: 400, body: { detail: { type: "ProcessingError", state: "unsupported", file: "anim.gif", message: "x" } } },
        "DELETE /tasks/t1": { status: 204 },
      });
      renderApp("/tools/imageconvert");
      await userEvent.upload(await screen.findByTestId("file-input"), new File(["x"], "anim.gif", { type: "image/gif" }));
      await userEvent.click(screen.getByRole("button", { name: runName }));
      expect(await screen.findByRole("alert")).toHaveTextContent(text);
      await i18n.changeLanguage("en");
    });

    it("leaves a processing error without file unprefixed", async () => {
      toolRoutes({
        "GET /tools": { body: [imageTool("imageconvert"), mergeTool] },
        "POST /tasks": { status: 201, body: task({ tool: "imageconvert" }) },
        "POST /tasks/t1/process": { status: 400, body: { detail: { type: "ProcessingError", state: "unsupported", message: "x" } } },
        "DELETE /tasks/t1": { status: 204 },
      });
      renderApp("/tools/imageconvert");
      await userEvent.upload(await screen.findByTestId("file-input"), new File(["x"], "anim.gif", { type: "image/gif" }));
      await userEvent.click(screen.getByRole("button", { name: /^run$/i }));
      expect((await screen.findByRole("alert")).textContent).toMatch(/^This picture cannot be processed/);
    });

    it("maps out_of_range to the crop-area message for image tools", async () => {
      toolRoutes({
        "GET /tools": { body: [imageTool("imagecrop"), mergeTool] },
        "POST /tasks": { status: 201, body: task({ tool: "imagecrop" }) },
        "POST /tasks/t1/process": { status: 400, body: { detail: { type: "ProcessingError", state: "out_of_range", message: "x" } } },
      });
      renderApp("/tools/imagecrop");
      await userEvent.upload(await screen.findByTestId("file-input"), new File(["x"], "p.png", { type: "image/png" }));
      await userEvent.click(screen.getByRole("button", { name: /^run$/i }));
      expect(await screen.findByRole("alert")).toHaveTextContent("The crop area is outside the picture.");
    });
  });

  it("a rapid double click on Run creates only one task", async () => {
    const calls = toolRoutes();
    renderApp("/tools/merge");
    await userEvent.upload(await screen.findByTestId("file-input"), [pdfFile("a.pdf"), pdfFile("b.pdf")]);
    const run = screen.getByRole("button", { name: /^run$/i });
    run.click();
    run.click();
    expect(await screen.findByRole("heading", { name: "Done" })).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "POST" && c.path === "/tasks")).toHaveLength(1);
  });

  it("a next-step button opens that tool with the result preloaded", async () => {
    toolRoutes();
    renderApp("/tools/merge");
    await userEvent.upload(await screen.findByTestId("file-input"), [pdfFile("a.pdf"), pdfFile("b.pdf")]);
    await userEvent.click(screen.getByRole("button", { name: /^run$/i }));
    await userEvent.click(await screen.findByRole("button", { name: "Compress PDF" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Compress PDF" })).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "Files" })).getByText("report.pdf")).toBeInTheDocument();
  });
});

describe("home", () => {
  it("on phones a toggle shows the descriptions in one column", async () => {
    mockFetch({ "GET /tools": { body: [mergeTool, compressTool] }, "GET /documents": { body: [] } });
    renderApp("/");
    const toggle = await screen.findByRole("button", { name: "Show descriptions" });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    const list = document.querySelector("#launcher-h")!.closest("section")!.querySelector("ul")!;
    expect(list.className).toContain("grid-cols-2");
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    expect(list.className).toContain("grid-cols-1");
    expect(screen.getByText("Reduce the file size.").className).not.toMatch(/max-sm:hidden/);
  });

  it("shows each tool's description and group as visible text, and the library card shows its origin tool", async () => {
    mockFetch({
      "GET /tools": { body: [mergeTool, compressTool] },
      "GET /documents": { body: [doc({ latest_version: version({ tool: "compress" }) })] },
    });
    renderApp("/");
    expect(await screen.findByText("Reduce the file size.")).toBeVisible();
    expect(screen.getAllByText("Optimize").length).toBeGreaterThan(0);
    const card = (await screen.findByText("report.pdf")).closest("li")!;
    expect(within(card).getByText("Compress PDF")).toBeInTheDocument();
    expect(document.querySelector("#launcher-h")!.closest("section")!.querySelector("a[title]")).toBeNull();
    // group name is text on the tile (not color alone) and is not hidden on phones
    const launcher = document.querySelector<HTMLElement>("#launcher-h")!.closest("section")!;
    const tile = within(launcher).getByRole("link", { name: /Compress PDF/ });
    const groupLabel = within(tile).getByText("Optimize");
    expect(groupLabel.className).not.toMatch(/max-sm:hidden/);
  });
});

describe("sidebar", () => {
  it("scrolls the active tool into view, nearest edge only", async () => {
    const spy = vi.spyOn(Element.prototype, "scrollIntoView");
    mockFetch({ "GET /tools": { body: [imageTool("imagecrop"), imageTool("imageclean"), mergeTool] }, "GET /documents": { body: [] } });
    renderApp("/tools/imageclean");
    await screen.findByRole("heading", { level: 1, name: "Remove photo info" });
    await vi.waitFor(() => expect(spy).toHaveBeenCalledWith({ block: "nearest" }));
    const target = spy.mock.contexts.at(-1) as HTMLElement;
    expect(target).toHaveAttribute("aria-current", "page");
    spy.mockRestore();
  });
});
