import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, pdfFile, renderApp, rotateTool } from "@/test/utils";
import type { Tool } from "@/lib/types";

const word2pdf: Tool = {
  ...rotateTool,
  id: "word2pdf",
  title: "Word to PDF",
  group: "office",
  description: "d",
  accepts: "office",
  extensions: ["docx", "odt"],
  requires: ["libreoffice"],
  available: true,
  params_schema: { properties: {} },
};
const pdf2word: Tool = { ...rotateTool, id: "pdf2word", title: "PDF to Word", group: "office", description: "d", params_schema: { properties: {} } };
const ocr: Tool = { ...rotateTool, id: "ocr", title: "OCR", group: "office", description: "d", params_schema: { properties: {} } };
const task = (over = {}) => ({ id: "t1", tool: "word2pdf", params: {}, state: "waiting", error: null, warnings: [], files: [], ...over });
const inFile = { id: "f1", role: "in", position: 0, filename: "a.docx", state: "ok", version_id: null, sha256: "x" };
const outFile = { id: "o1", role: "out", position: 0, filename: "a.pdf", state: "ok", version_id: null, sha256: "y", size: 2048 };
const docx = () => new File(["PK"], "a.docx");

function routes(tools: Tool[], process: unknown) {
  return mockFetch({
    "GET /tools": { body: tools },
    "GET /documents": { body: [] },
    "POST /tasks": { status: 201, body: task() },
    "POST /tasks/t1/files": { status: 201, body: task({ files: [inFile] }) },
    "POST /tasks/t1/process": process as { status?: number; body?: unknown },
    "DELETE /tasks/t1": { status: 204 },
  });
}

describe("office tools", () => {
  it("shows the honest-quality note before running a PDF -> Office tool", async () => {
    routes([pdf2word], { body: task() });
    renderApp("/tools/pdf2word");
    const note = await screen.findByRole("note");
    expect(note).toHaveTextContent("not pixel-perfect");
  });

  it("disables the tool with a reason when LibreOffice is missing", async () => {
    routes([{ ...word2pdf, available: false }], { body: task() });
    renderApp("/tools/word2pdf");
    expect(await screen.findByText(/LibreOffice is not available here/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Select files" })).toBeDisabled();
    expect(screen.getByRole("button", { name: /^run$/i })).toBeDisabled();
  });

  it("lists the warnings of a finished task, with an action when the tool exists", async () => {
    const warnings = [
      { code: "font_substituted", params: { fonts: "Calibri" } },
      { code: "no_text_layer", params: { pages: "2" }, action: { tool: "ocr" } },
      { code: "something_new" },
    ];
    routes([word2pdf, ocr], { body: task({ state: "success", files: [inFile, outFile], warnings }) });
    renderApp("/tools/word2pdf");
    await userEvent.upload(await screen.findByTestId("file-input"), docx());
    await userEvent.click(screen.getByRole("button", { name: /^run$/i }));
    expect(await screen.findByRole("heading", { name: "Done, with 3 heads-up" })).toBeInTheDocument();
    const list = screen.getByRole("list", { name: "Check these things" });
    expect(list).toHaveTextContent("similar ones were used: Calibri");
    expect(list).toHaveTextContent("Pages 2 look scanned");
    expect(list).toHaveTextContent("Something may look different from the original.");
    expect(screen.getByRole("link", { name: "Open OCR" })).toHaveAttribute("href", "/tools/ocr");
  });

  it("offers Retry and an office-specific message when the converter is busy", async () => {
    routes([word2pdf], {
      status: 503,
      body: { detail: { state: "busy", message: "The server is busy. Try again in a moment.", retryable: true } },
    });
    renderApp("/tools/word2pdf");
    await userEvent.upload(await screen.findByTestId("file-input"), docx());
    await userEvent.click(screen.getByRole("button", { name: /^run$/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Another document is being converted right now");
    expect(screen.getByRole("button", { name: "Retry" })).toBeEnabled();
  });

  it("names office upload problems in document words, not picture words", async () => {
    mockFetch({
      "GET /tools": { body: [word2pdf] },
      "GET /documents": { body: [] },
      "POST /tasks": { status: 201, body: task() },
      "POST /tasks/t1/files": { status: 422, body: { detail: { state: "macro", message: "macros" } } },
      "DELETE /tasks/t1": { status: 204 },
    });
    renderApp("/tools/word2pdf");
    await userEvent.upload(await screen.findByTestId("file-input"), docx());
    await userEvent.click(screen.getByRole("button", { name: /^run$/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("contains macros");
  });

  it("marks tools without their engine in the launcher, but keeps them visible", async () => {
    routes([{ ...word2pdf, available: false }, pdf2word], { body: task() });
    renderApp("/");
    await screen.findByRole("heading", { name: /tools/i });
    const launcher = within(document.querySelector<HTMLElement>("#launcher-h")!.closest("section")!);
    expect(await launcher.findByRole("link", { name: /Word to PDF/ })).toHaveTextContent("Needs LibreOffice");
    expect(launcher.getByRole("link", { name: /PDF to Word/ })).not.toHaveTextContent("Needs LibreOffice");
  });

  it("keeps the PDF library picker for PDF -> Office tools only", async () => {
    routes([pdf2word, word2pdf], { body: task() });
    renderApp("/tools/pdf2word");
    expect(await screen.findByRole("button", { name: "From library" })).toBeInTheDocument();
    await userEvent.upload(screen.getByTestId("file-input"), pdfFile());
  });
});
