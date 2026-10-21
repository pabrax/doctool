export interface JsonSchemaProp {
  type?: string;
  title?: string;
  description?: string;
  default?: unknown;
  enum?: (string | number)[];
  minimum?: number;
  maximum?: number;
  exclusiveMinimum?: number;
  exclusiveMaximum?: number;
  minLength?: number;
  pattern?: string;
  anyOf?: JsonSchemaProp[];
  items?: JsonSchemaProp;
  secret?: boolean;
  show_when?: Record<string, (string | number)[]>;
}

export interface ParamsSchema {
  properties?: Record<string, JsonSchemaProp>;
  required?: string[];
}

export interface Tool {
  id: string;
  title: string;
  group: string;
  description: string;
  accepts: "pdf" | "image" | "pdf+image";
  min_files: number;
  max_files: number | null;
  params_schema: ParamsSchema;
}

export interface Version {
  id: string;
  document_id: string;
  seq: number;
  parent_version_id: string | null;
  filename: string;
  sha256: string;
  size: number;
  pages: number | null;
  encrypted: boolean;
  tool: string | null;
  params: Record<string, unknown> | null;
  created_at: string;
}

export interface Doc {
  id: string;
  name: string;
  tags: string[];
  created_at: string;
  latest_version: Version;
}

export interface TaskFile {
  id: string;
  role: "in" | "out";
  position: number;
  version_id: string | null;
  filename: string;
  sha256: string | null;
  state: string;
}

export interface Task {
  id: string;
  tool: string;
  params: Record<string, unknown>;
  state: "waiting" | "processing" | "success" | "error";
  error: string | null;
  files: TaskFile[];
}

export interface PageInfo {
  index: number;
  width: number;
  height: number;
  rotate: number;
}

/** A file the user has queued for a tool: a local upload or an existing library version. */
export interface InputRef {
  key: string;
  name: string;
  file?: File;
  versionId?: string;
  pages?: number | null;
  size?: number;
}
