import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { doc, mergeTool, mockFetch, pdfFile, renderApp, rotateTool, version } from "@/test/utils";

const task = (over = {}) => ({
  id: "t1",
  tool: "rotate",
  params: {},
  state: "waiting",
  error: null,
  files: [],
  ...over,
});

describe("Library page", () => {
  it("lists documents, filters by name or tag, and shows the empty state", async () => {
    mockFetch({
      "GET /tools": { body: [rotateTool] },
      "GET /documents": {
        body: [
          doc({ id: "d1", name: "invoice.pdf", tags: ["finance"] }),
          doc({ id: "d2", name: "notes.pdf", latest_version: version({ id: "v2", document_id: "d2", pages: 1 }) }),
        ],
      },
    });
    renderApp("/");
    expect(await screen.findByText("invoice.pdf")).toBeInTheDocument();
    expect(screen.getByText("notes.pdf")).toBeInTheDocument();

    await userEvent.type(screen.getByRole("searchbox"), "financ");
    expect(screen.getByText("invoice.pdf")).toBeInTheDocument();
    expect(screen.queryByText("notes.pdf")).not.toBeInTheDocument();

    await userEvent.clear(screen.getByRole("searchbox"));
    await userEvent.type(screen.getByRole("searchbox"), "zzz");
    expect(screen.getByText(/nothing matches|nada coincide/i)).toBeInTheDocument();
  });

  it("shows an empty-library message", async () => {
    mockFetch({ "GET /tools": { body: [] }, "GET /documents": { body: [] } });
    renderApp("/");
    expect(await screen.findByText(/no documents yet|aún no hay documentos/i)).toBeInTheDocument();
  });

  it("deletes a document only after confirmation", async () => {
    const calls = mockFetch({
      "GET /tools": { body: [] },
      "GET /documents": { body: [doc({ name: "old.pdf" })] },
      "DELETE /documents/d1": { status: 204 },
    });
    const confirm = vi.spyOn(window, "confirm");
    renderApp("/");
    const btn = await screen.findByRole("button", { name: /(delete|eliminar): old\.pdf/i });
    confirm.mockReturnValueOnce(false);
    await userEvent.click(btn);
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
    confirm.mockReturnValueOnce(true);
    await userEvent.click(btn);
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE" && c.path === "/documents/d1")).toBe(true));
  });

  it("has no detectable accessibility violations", async () => {
    mockFetch({ "GET /tools": { body: [rotateTool] }, "GET /documents": { body: [doc()] } });
    const { container } = renderApp("/");
    await screen.findByText("report.pdf");
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe("Tool page", () => {
  it("uploads, runs the task contract in order and offers the download", async () => {
    const calls = mockFetch({
      "GET /tools": { body: [rotateTool, mergeTool] },
      "GET /documents": { body: [] },
      "POST /tasks": { status: 201, body: task() },
      "POST /tasks/t1/files": { status: 201, body: task({ files: [{ id: "f1", role: "in", position: 0, filename: "a.pdf", state: "ok", version_id: null, sha256: "x" }] }) },
      "POST /tasks/t1/process": {
        body: task({ state: "success", files: [{ id: "o1", role: "out", position: 0, filename: "a.pdf", state: "ok", version_id: "v9", sha256: "y" }] }),
      },
      "GET /versions/v9": { body: version({ id: "v9", document_id: "d9", seq: 2, tool: "rotate" }) },
    });
    renderApp("/tools/rotate");
    expect(await screen.findByRole("heading", { level: 1, name: /rotate pdf|rotar pdf/i })).toBeInTheDocument();

    const run = screen.getByRole("button", { name: /^(run|ejecutar)$/i });
    expect(run).toBeDisabled();

    await userEvent.upload(screen.getByTestId("file-input"), pdfFile("a.pdf"));
    expect(await screen.findByText("a.pdf")).toBeInTheDocument();
    await userEvent.click(run);

    const link = await screen.findByRole("link", { name: /download|descargar/i });
    expect(link).toHaveAttribute("href", "/api/v1/tasks/t1/download");
    expect(calls.map((c) => `${c.method} ${c.path}`).filter((c) => c.startsWith("POST"))).toEqual([
      "POST /tasks",
      "POST /tasks/t1/files",
      "POST /tasks/t1/process",
    ]);
    expect((calls[1 + calls.findIndex((c) => c.path === "/tasks")].body as FormData).get("file")).toBeInstanceOf(File);
    expect(await screen.findByRole("link", { name: /open in library|abrir en la biblioteca/i })).toHaveAttribute("href", "/library/d9");
  });

  it("sends the chosen options with the task", async () => {
    const calls = mockFetch({
      "GET /tools": { body: [rotateTool] },
      "GET /documents": { body: [] },
      "POST /tasks": { status: 201, body: task() },
      "POST /tasks/t1/files": { status: 201, body: task({ files: [{ id: "f1", role: "in", position: 0, filename: "a.pdf", state: "ok", version_id: null, sha256: "x" }] }) },
      "POST /tasks/t1/process": { body: task({ state: "success", files: [] }) },
    });
    renderApp("/tools/rotate");
    await userEvent.upload(await screen.findByTestId("file-input"), pdfFile());
    await userEvent.selectOptions(screen.getByRole("combobox", { name: /angle|ángulo/i }), "180");
    await userEvent.clear(screen.getByLabelText(/^(pages|páginas)$/i));
    await userEvent.type(screen.getByLabelText(/^(pages|páginas)$/i), "2-3");
    await userEvent.click(screen.getByRole("button", { name: /^(run|ejecutar)$/i }));
    await waitFor(() => expect(calls.some((c) => c.path === "/tasks/t1/process")).toBe(true));
    expect(calls.find((c) => c.method === "POST" && c.path === "/tasks")!.body).toEqual({
      tool: "rotate",
      params: { angle: 180, pages: "2-3" },
    });
  });

  it("asks for a password on wrong_password and retries with it", async () => {
    let attempt = 0;
    let n = 0;
    const calls = mockFetch({
      "GET /tools": { body: [rotateTool] },
      "GET /documents": { body: [] },
      "POST /tasks": () => ({ status: 201, body: task({ id: `t${++n}` }) }),
      "POST /tasks/t\\d/files": (c) => ({
        status: 201,
        body: task({ id: c.path.split("/")[2], files: [{ id: "f1", role: "in", position: 0, filename: "a.pdf", state: "ok", version_id: null, sha256: "x" }] }),
      }),
      "POST /tasks/t\\d/process": (c) => {
        attempt++;
        if (attempt === 1) return { status: 400, body: { detail: { type: "ProcessingError", state: "wrong_password", message: "password required" } } };
        return { body: task({ id: c.path.split("/")[2], state: "success", files: [] }) };
      },
      "DELETE /tasks/t\\d": { status: 204 },
    });
    renderApp("/tools/rotate");
    await userEvent.upload(await screen.findByTestId("file-input"), pdfFile("a.pdf"));
    await userEvent.click(screen.getByRole("button", { name: /^(run|ejecutar)$/i }));

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText(/need a password|necesitan contraseña/i)).toBeInTheDocument();
    const pw = screen.getByLabelText(/password for a\.pdf|contraseña de a\.pdf/i);
    await userEvent.type(pw, "s3cret");
    await userEvent.click(screen.getByRole("button", { name: /(retry|reintentar)/i }));

    await screen.findByRole("link", { name: /download|descargar/i });
    const second = calls.filter((c) => c.method === "POST" && /\/process$/.test(c.path)).at(-1)!;
    expect(second.body).toEqual({ passwords: { f1: "s3cret" }, save_to_library: true });
  });

  it("shows a friendly message for a damaged file", async () => {
    mockFetch({
      "GET /tools": { body: [rotateTool] },
      "GET /documents": { body: [] },
      "POST /tasks": { status: 201, body: task() },
      "POST /tasks/t1/files": { status: 201, body: task({ files: [{ id: "f1", role: "in", position: 0, filename: "a.pdf", state: "ok", version_id: null, sha256: "x" }] }) },
      "POST /tasks/t1/process": { status: 400, body: { detail: { type: "ProcessingError", state: "damaged", message: "x" } } },
      "DELETE /tasks/t1": { status: 204 },
    });
    renderApp("/tools/rotate");
    await userEvent.upload(await screen.findByTestId("file-input"), pdfFile());
    await userEvent.click(screen.getByRole("button", { name: /^(run|ejecutar)$/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/damaged|dañado/i);
  });

  it("requires the minimum number of files and lets you reorder with the buttons", async () => {
    mockFetch({ "GET /tools": { body: [mergeTool] }, "GET /documents": { body: [] } });
    renderApp("/tools/merge");
    const input = await screen.findByTestId("file-input");
    await userEvent.upload(input, pdfFile("one.pdf"));
    const run = screen.getByRole("button", { name: /^(run|ejecutar)$/i });
    expect(run).toBeDisabled();
    await userEvent.upload(input, pdfFile("two.pdf"));
    expect(run).toBeEnabled();

    const names = () =>
      within(screen.getByRole("list", { name: /^(files|archivos)$/i }))
        .getAllByRole("listitem")
        .map((li) => li.textContent ?? "");
    expect(names()[0]).toContain("one.pdf");
    await userEvent.click(screen.getByRole("button", { name: /(move down|bajar): one\.pdf/i }));
    expect(names()[0]).toContain("two.pdf");
    await userEvent.click(screen.getByRole("button", { name: /(remove|quitar): two\.pdf/i }));
    expect(screen.queryByText("two.pdf")).not.toBeInTheDocument();
    expect(run).toBeDisabled();
  });

  it("rejects files the tool cannot use", async () => {
    mockFetch({ "GET /tools": { body: [rotateTool] }, "GET /documents": { body: [] } });
    renderApp("/tools/rotate");
    const input = await screen.findByTestId("file-input");
    await userEvent.upload(input, new File(["x"], "a.txt", { type: "text/plain" }), { applyAccept: false });
    expect(screen.queryByText("a.txt")).not.toBeInTheDocument();
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("has no detectable accessibility violations", async () => {
    mockFetch({ "GET /tools": { body: [rotateTool] }, "GET /documents": { body: [] } });
    const { container } = renderApp("/tools/rotate");
    await screen.findByRole("heading", { level: 1 });
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe("Document page", () => {
  it("shows history, preview and sends the version to a tool", async () => {
    const v1 = version({ id: "v1", seq: 1 });
    const v2 = version({ id: "v2", seq: 2, tool: "rotate", parent_version_id: "v1" });
    mockFetch({
      "GET /tools": { body: [rotateTool] },
      "GET /documents/d1": { body: doc({ latest_version: v2 }) },
      "GET /documents/d1/versions": { body: [v1, v2] },
      "GET /versions/v2/metadata": { body: { pages: 3, size: 2048, info: { Title: "Hello" } } },
      "GET /versions/v1/metadata": { body: { pages: 3, size: 2048, info: {} } },
    });
    renderApp("/library/d1");
    expect(await screen.findByRole("heading", { level: 1, name: "report.pdf" })).toBeInTheDocument();
    expect(screen.getByTitle(/preview|vista previa/i)).toHaveAttribute("src", "/api/v1/versions/v2/download?inline=1");
    expect(await screen.findByText("Hello")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem").length).toBeGreaterThanOrEqual(2); // history entries
    await userEvent.click(screen.getByRole("button", { name: /version 1|versión 1/i }));
    expect(screen.getByTitle(/preview|vista previa/i)).toHaveAttribute("src", "/api/v1/versions/v1/download?inline=1");
  });
});
