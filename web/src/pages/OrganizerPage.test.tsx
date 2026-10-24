import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { doc, mockFetch, renderApp, rotateTool, version } from "@/test/utils";

const organizeTool = { ...rotateTool, id: "organize", title: "Organize pages", params_schema: { properties: {} } };
const pages = (n: number) =>
  Array.from({ length: n }, (_, i) => ({ index: i + 1, width: 595, height: 842, rotate: 0 }));

function setup(extra: Record<string, never | object> = {}) {
  return mockFetch({
    "GET /tools": { body: [organizeTool] },
    "GET /documents": { body: [doc()] },
    "GET /versions/v1": { body: version() },
    "GET /versions/v1/pages": { body: pages(3) },
    ...extra,
  });
}

const cards = () => within(screen.getByRole("list", { name: /pages|páginas/i })).getAllByRole("listitem");

describe("Organizer page", () => {
  it("without a document, lets you pick one from the library", async () => {
    setup();
    renderApp("/organize");
    const pick = await screen.findByRole("button", { name: /report\.pdf/i });
    await userEvent.click(pick);
    expect(await screen.findAllByRole("img")).not.toHaveLength(0);
    expect(await screen.findByRole("list", { name: /pages|páginas/i })).toBeInTheDocument();
  });

  it("renders one thumbnail per page from the server", async () => {
    setup();
    renderApp("/organize/v1");
    await waitFor(() => expect(cards()).toHaveLength(3));
    const imgs = within(screen.getByRole("list", { name: /pages|páginas/i })).getAllByRole("img");
    expect(imgs[0]).toHaveAttribute("src", "/api/v1/versions/v1/thumbnail/1?width=240");
    expect(imgs[2]).toHaveAttribute("src", "/api/v1/versions/v1/thumbnail/3?width=240");
  });

  it("deletes, duplicates, adds blank pages and resets", async () => {
    setup();
    renderApp("/organize/v1");
    await waitFor(() => expect(cards()).toHaveLength(3));

    await userEvent.click(screen.getByRole("button", { name: /(delete page|eliminar página).*1/i }));
    expect(cards()).toHaveLength(2);
    await userEvent.click(screen.getByRole("button", { name: /(duplicate|duplicar).*2/i }));
    expect(cards()).toHaveLength(3);
    await userEvent.click(screen.getByRole("button", { name: /(add blank page|añadir página en blanco)/i }));
    expect(cards()).toHaveLength(4);
    expect(within(cards()[3]).getByText(/^4\. (blank|en blanco)$/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /^(reset|restablecer)$/i }));
    expect(cards()).toHaveLength(3);
  });

  it("reorders with the move buttons (keyboard alternative to dragging)", async () => {
    const calls = setup({
      "POST /tasks": { status: 201, body: { id: "t1", tool: "organize", params: {}, state: "waiting", error: null, files: [] } },
      "POST /tasks/t1/files": { status: 201, body: { id: "t1", tool: "organize", params: {}, state: "waiting", error: null, files: [] } },
      "POST /tasks/t1/process": {
        body: {
          id: "t1", tool: "organize", params: {}, state: "success", error: null,
          files: [{ id: "o", role: "out", position: 0, version_id: "v2", filename: "x.pdf", sha256: "s", state: "ok" }],
        },
      },
      "GET /versions/v2": { body: version({ id: "v2", seq: 2, tool: "organize" }) },
      "GET /documents/d1": { body: doc({ latest_version: version({ id: "v2", seq: 2 }) }) },
      "GET /documents/d1/versions": { body: [version(), version({ id: "v2", seq: 2 })] },
      "GET /versions/v2/metadata": { body: { pages: 3, size: 1, info: {} } },
    });
    renderApp("/organize/v1");
    await waitFor(() => expect(cards()).toHaveLength(3));

    await userEvent.click(screen.getByRole("button", { name: /(move right|mover a la derecha).*1/i }));
    await userEvent.click(screen.getByRole("button", { name: /(rotate right|rotar a la derecha).*3/i }));
    await userEvent.click(screen.getByRole("button", { name: /(apply|aplicar)/i }));

    await waitFor(() => expect(calls.some((c) => c.path === "/tasks/t1/process")).toBe(true));
    const create = calls.find((c) => c.method === "POST" && c.path === "/tasks")!;
    expect(create.body).toEqual({ tool: "organize", params: { order: [2, 1, 3], rotate: [0, 0, 90] } });
    expect((calls.find((c) => c.path === "/tasks/t1/files")!.body as FormData).get("version_id")).toBe("v1");
    // lands on the document page, showing the new version
    expect(await screen.findByRole("heading", { level: 1, name: "report.pdf" })).toBeInTheDocument();
  });

  it("only enables Apply when something changed", async () => {
    setup();
    renderApp("/organize/v1");
    await waitFor(() => expect(cards()).toHaveLength(3));
    const apply = screen.getByRole("button", { name: /(apply|aplicar)/i });
    expect(apply).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: /(rotate left|rotar a la izquierda).*2/i }));
    expect(apply).toBeEnabled();
    await userEvent.click(screen.getByRole("button", { name: /(rotate right|rotar a la derecha).*2/i }));
    expect(apply).toBeDisabled(); // rotating back to 0 is "no change"
  });

  it("will not let you delete every page", async () => {
    mockFetch({
      "GET /tools": { body: [organizeTool] },
      "GET /versions/v1": { body: version({ pages: 1 }) },
      "GET /versions/v1/pages": { body: pages(1) },
    });
    renderApp("/organize/v1");
    await waitFor(() => expect(cards()).toHaveLength(1));
    await userEvent.click(screen.getByRole("button", { name: /(delete page|eliminar página)/i }));
    expect(cards()).toHaveLength(1);
  });

  it("explains encrypted documents instead of failing", async () => {
    mockFetch({
      "GET /tools": { body: [organizeTool] },
      "GET /versions/v1": { body: version({ encrypted: true, pages: null }) },
    });
    renderApp("/organize/v1");
    expect(await screen.findByText(/encrypted|cifrado/i)).toBeInTheDocument();
  });

  it("has no detectable accessibility violations", async () => {
    setup();
    const { container } = renderApp("/organize/v1");
    await waitFor(() => expect(cards()).toHaveLength(3));
    expect(await axe(container)).toHaveNoViolations();
  });
});
