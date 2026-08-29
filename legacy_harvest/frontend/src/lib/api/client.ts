import { apiBaseUrl } from "../../config/env";
import { ApiError } from "./errors";

function errorKind(status: number): "validation" | "not-found" | "permission" | "server" | "unexpected" { if (status === 404) return "not-found"; if (status === 401 || status === 403) return "permission"; if (status === 422) return "validation"; if (status >= 500) return "server"; return "unexpected"; }
async function readBody(response: Response): Promise<unknown> { const text = await response.text(); if (!text) return undefined; try { return JSON.parse(text); } catch { return text; } }

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try { response = await fetch(`${apiBaseUrl}/api/v1${path}`, { ...init, headers: { Accept: "application/json", ...init.headers } }); }
    catch { throw new ApiError("network", undefined, "Network connection failed. Please retry."); }
  const body = await readBody(response);
  if (!response.ok) { const message = typeof body === "object" && body && "detail" in body ? String(body.detail) : `Request failed (${response.status})`; throw new ApiError(errorKind(response.status), response.status, message); }
  if (response.status === 204 || body === undefined) return undefined as T;
  return body as T;
}
export const get = <T>(path: string) => request<T>(path);
export const post = <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", headers: body === undefined ? undefined : { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
export const put = <T>(path: string, body: unknown) => request<T>(path, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const patch = <T>(path: string, body: unknown) => request<T>(path, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const del = <T>(path: string) => request<T>(path, { method: "DELETE" });
export async function postForm<T>(path: string, body: FormData): Promise<T> { return request<T>(path, { method: "POST", body }); }
