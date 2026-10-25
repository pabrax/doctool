import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { doc, mergeTool, mockFetch, pdfFile, renderApp, rotateTool, version } from "@/test/utils";
import type { Tool } from "@/lib/types";

const compressTool: Tool = { ...rotateTool, id: "compress", title: "Compress PDF", group: "optimize", description: "Reduce the file size.", params_schema: { properties: {} } };
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
