import {
  type ApiResult,
  createPublicApi,
  type FormDetail,
  type Forms,
  type RequestOptions,
} from "./api";

function backendOrigin(): string | null {
  try {
    const value = process.env.API_BASE_URL;
    if (!value) return null;
    const url = new URL(value);
    const local = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
    if (
      (url.protocol !== "https:" && !(local && url.protocol === "http:")) ||
      url.username ||
      url.password ||
      url.pathname !== "/" ||
      url.search ||
      url.hash
    )
      return null;
    return url.origin;
  } catch {
    return null;
  }
}
// Read configuration only when a loader calls the API, never during build.
export function listForms(
  options: RequestOptions = {},
): Promise<ApiResult<Forms>> {
  const origin = backendOrigin();
  return origin
    ? createPublicApi(origin).listForms(options)
    : Promise.resolve({ ok: false, kind: "configuration" });
}
export function getForm(
  id: string,
  options: RequestOptions = {},
): Promise<ApiResult<FormDetail>> {
  const origin = backendOrigin();
  return origin
    ? createPublicApi(origin).getForm(id, options)
    : Promise.resolve({ ok: false, kind: "configuration" });
}
