import type { Doc, PageInfo, Task, Tool, Version } from "./types";

const BASE = "/api/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    /** Documented per-file state (wrong_password, damaged, out_of_range...) when the API sent one. */
    public state?: string,
  ) {
    super(message);
  }
}

function describe(detail: unknown): { message: string; state?: string } {
  if (typeof detail === "string") return { message: detail };
  if (Array.isArray(detail)) {
    const msg = detail
      .map((d: { loc?: (string | number)[]; msg?: string }) =>
        [d.loc?.join("."), d.msg].filter(Boolean).join(": "),
      )
      .join("; ");
    return { message: msg || "Invalid request", state: "invalid" };
  }
  if (detail && typeof detail === "object") {
    const d = detail as { state?: string; message?: string };
    return { message: d.message ?? "Request failed", state: d.state };
  }
  return { message: "Request failed" };
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + path, init);
  } catch {
    throw new ApiError(0, "Cannot reach the doctool server", "network");
  }
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = res.statusText;
    }
    const { message, state } = describe(detail);
    throw new ApiError(res.status, message, state);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  tools: () => req<Tool[]>("/tools"),
  documents: () => req<Doc[]>("/documents"),
  document: (id: string) => req<Doc>(`/documents/${id}`),
  versions: (id: string) => req<Version[]>(`/documents/${id}/versions`),
  version: (id: string) => req<Version>(`/versions/${id}`),
  pages: (versionId: string) => req<PageInfo[]>(`/versions/${versionId}/pages`),
  metadata: (versionId: string) =>
    req<{ pages: number; size: number; info: Record<string, string> }>(
      `/versions/${versionId}/metadata`,
    ),
  uploadDocument(file: File) {
    const form = new FormData();
    form.append("file", file);
    return req<Doc>("/documents", { method: "POST", body: form });
  },
  patchDocument: (id: string, body: { name?: string; tags?: string[] }) =>
    req<Doc>(`/documents/${id}`, { ...json(body), method: "PATCH" }),
  deleteDocument: (id: string) => req<void>(`/documents/${id}`, { method: "DELETE" }),

  createTask: (tool: string, params: Record<string, unknown>) =>
    req<Task>("/tasks", json({ tool, params })),
  addTaskFile(taskId: string, input: { file?: File; versionId?: string }) {
    const form = new FormData();
    if (input.file) form.append("file", input.file);
    if (input.versionId) form.append("version_id", input.versionId);
    return req<Task>(`/tasks/${taskId}/files`, { method: "POST", body: form });
  },
  process: (taskId: string, passwords: Record<string, string> = {}, saveToLibrary = true) =>
    req<Task>(
      `/tasks/${taskId}/process`,
      json({ passwords, save_to_library: saveToLibrary }),
    ),
  deleteTask: (taskId: string) => req<void>(`/tasks/${taskId}`, { method: "DELETE" }),

  taskDownloadUrl: (taskId: string) => `${BASE}/tasks/${taskId}/download`,
  versionDownloadUrl: (id: string, inline = false) =>
    `${BASE}/versions/${id}/download${inline ? "?inline=1" : ""}`,
  thumbnailUrl: (id: string, page = 1, width = 240) =>
    `${BASE}/versions/${id}/thumbnail/${page}?width=${width}`,
};
