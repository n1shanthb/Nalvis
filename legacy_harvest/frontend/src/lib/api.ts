/** Compatibility export while feature APIs migrate to lib/api/client. */
export { request as api } from "./api/client";
export type JsonObject = Record<string, any>;
export const json = (value: unknown) => JSON.stringify(value, null, 2);
