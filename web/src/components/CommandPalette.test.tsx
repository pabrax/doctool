import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { doc, mergeTool, mockFetch, renderApp, rotateTool } from "@/test/utils";

const setup = () =>
  mockFetch({
    "GET /tools": { body: [rotateTool, mergeTool] },
    "GET /documents": { body: [doc({ id: "d7", name: "contract.pdf" })] },
  });

describe("Command palette", () => {
  it("opens with Ctrl+K, filters, and navigates to a tool with Enter", async () => {
    setup();
    renderApp("/");
    await screen.findByRole("heading", { level: 1 });
    await userEvent.keyboard("{Control>}k{/Control}");
    const input = await screen.findByRole("combobox");
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    await userEvent.type(input, "merge");
    expect(await screen.findByRole("option", { name: /merge pdf|unir pdf/i })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: /rotate pdf|rotar pdf/i })).not.toBeInTheDocument();

    await userEvent.keyboard("{Enter}");
    expect(await screen.findByRole("heading", { level: 1, name: /merge pdf|unir pdf/i })).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("finds library documents and opens them", async () => {
    setup();
    renderApp("/tools/rotate");
    await screen.findByRole("heading", { level: 1 });
    await userEvent.click(screen.getByRole("button", { name: /command palette|paleta de comandos/i }));
    await userEvent.type(await screen.findByRole("combobox"), "contract");
    await userEvent.click(await screen.findByRole("option", { name: /contract\.pdf/i }));
    expect(await screen.findByText(/document not found|documento no encontrado|loading|cargando/i)).toBeInTheDocument();
  });

  it("closes with Escape and shows an empty state for no matches", async () => {
    setup();
    renderApp("/");
    await screen.findByRole("heading", { level: 1 });
    await userEvent.keyboard("{Control>}k{/Control}");
    await userEvent.type(await screen.findByRole("combobox"), "qqqqqq");
    expect(await screen.findByText(/no results|sin resultados/i)).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("has no detectable accessibility violations when open", async () => {
    setup();
    renderApp("/");
    await screen.findByRole("heading", { level: 1 });
    await userEvent.keyboard("{Control>}k{/Control}");
    await screen.findByRole("combobox");
    expect(await axe(document.body)).toHaveNoViolations();
  });
});
