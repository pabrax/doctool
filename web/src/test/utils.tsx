import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { App } from "@/App";
import "@/i18n";
import type { Doc, Tool, Version } from "@/lib/types";

export interface Call {
  method: string;
  path: string;
  body?: unknown;
}
type Handler = (call: Call) => { status?: number; body?: unknown } | undefined;

/** Install a fake fetch. Handlers are tried in order; unmatched requests fail the test loudly. */
export function mockFetch(handlers: Record<string, Handler | { status?: number; body?: unknown }>) {
  const calls: Call[] = [];
  globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const path = url.replace(/^.*\/api\/v1/, "");
    const method = (init?.method ?? "GET").toUpperCase();
    let body: unknown = init?.body;
    if (typeof body === "string") {
      try {
        body = JSON.parse(body);
      } catch {
        /* keep raw */
      }
    }
    const call: Call = { method, path, body };
    calls.push(call);
    const key = Object.keys(handlers).find((k) => {
      const [m, p] = k.split(" ");
      return m === method && (p === path || new RegExp(`^${p}$`).test(path));
    });
    if (!key) throw new Error(`Unmocked request: ${method} ${path}`);
    const h = handlers[key];
    const out = typeof h === "function" ? h(call) : h;
    const status = out?.status ?? 200;
    return new Response(status === 204 ? null : JSON.stringify(out?.body ?? {}), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  }) as typeof fetch;
  return calls;
}

export function renderApp(path = "/") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

export const version = (over: Partial<Version> = {}): Version => ({
  id: "v1",
  document_id: "d1",
  seq: 1,
  parent_version_id: null,
  filename: "report.pdf",
  sha256: "a".repeat(64),
  size: 2048,
  pages: 3,
  encrypted: false,
  tool: null,
  params: null,
  created_at: "2026-10-21T10:00:00Z",
  ...over,
});

export const doc = (over: Partial<Doc> = {}): Doc => ({
  id: "d1",
  name: "report.pdf",
  tags: [],
  created_at: "2026-10-21T10:00:00Z",
  latest_version: version(),
  ...over,
});

export const rotateTool: Tool = {
  id: "rotate",
  title: "Rotate PDF",
  group: "organize",
  description: "Rotate",
  accepts: "pdf",
  min_files: 1,
  max_files: 1,
  params_schema: {
    properties: {
      angle: { type: "integer", enum: [90, 180, 270], default: 90 },
      pages: { type: "string", default: "all" },
    },
  },
};

export const mergeTool: Tool = {
  ...rotateTool,
  id: "merge",
  title: "Merge PDF",
  min_files: 2,
  max_files: null,
  params_schema: { properties: {} },
};

export const pdfFile = (name = "a.pdf") => new File(["%PDF-1.7"], name, { type: "application/pdf" });
