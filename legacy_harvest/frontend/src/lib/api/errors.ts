export type ApiErrorKind = "network" | "validation" | "not-found" | "permission" | "server" | "unexpected";

export class ApiError extends Error {
  constructor(public readonly kind: ApiErrorKind, public readonly status?: number, message = "Unexpected request failure") { super(message); this.name = "ApiError"; }
}

export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  if (error instanceof TypeError) return new ApiError("network", undefined, "Network connection failed. Please retry.");
  return new ApiError("unexpected", undefined, "Unexpected error. Please retry.");
}
