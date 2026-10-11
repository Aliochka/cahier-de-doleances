import type {
  components,
  operations,
  paths,
} from "../../contracts/api.generated";

export const API_TIMEOUT_MS = 20_000;
export const LONG_WAIT_MS = 8_000;
export type ApiErrorKind =
  | "request"
  | "denied"
  | "missing"
  | "application"
  | "unavailable"
  | "server_timeout"
  | "timeout"
  | "network"
  | "cancelled"
  | "invalid_response"
  | "configuration";
export type ApiFailure = { ok: false; kind: ApiErrorKind; status?: number };
export type ApiResult<T> = { ok: true; data: T } | ApiFailure;
export type RequestOptions = {
  signal?: AbortSignal;
  timeoutMs?: number;
  query?: URLSearchParams;
};
export type Forms =
  operations["list_public_forms"]["responses"][200]["content"]["application/json"];
export type FormDetail =
  operations["get_public_form"]["responses"][200]["content"]["application/json"];
type FormSummary = components["schemas"]["FormSummary"];

export function httpFailure(status: number): ApiFailure {
  const kind =
    status === 400 || status === 422
      ? "request"
      : status === 401 || status === 403
        ? "denied"
        : status === 404
          ? "missing"
          : status === 502 || status === 503
            ? "unavailable"
            : status === 504 || status === 408
              ? "server_timeout"
              : "application";
  return { ok: false, kind, status };
}
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
function publicId(value: unknown): value is string {
  return typeof value === "string" && /^\d+$/.test(value);
}
function summary(value: unknown): value is FormSummary {
  return (
    record(value) &&
    publicId(value.id) &&
    typeof value.name === "string" &&
    typeof value.questions_count === "number" &&
    Number.isInteger(value.questions_count) &&
    value.questions_count >= 0 &&
    typeof value.url === "string"
  );
}
function forms(value: unknown): value is Forms {
  return Array.isArray(value) && value.every(summary);
}
function detail(value: unknown): value is FormDetail {
  if (!record(value)) return false;
  const questions = value.questions;
  return (
    summary(value) &&
    record(value) &&
    Array.isArray(questions) &&
    questions.every(
      (q: unknown) =>
        record(q) &&
        publicId(q.id) &&
        publicId(q.form_id) &&
        typeof q.prompt === "string" &&
        typeof q.type === "string" &&
        (q.position === null ||
          (typeof q.position === "number" && Number.isInteger(q.position))) &&
        typeof q.slug === "string" &&
        typeof q.url === "string",
    )
  );
}

/** Read-only public transport. It never forwards account cookies or API error bodies. */
export function createPublicApi(origin = "", transport: typeof fetch = fetch) {
  async function read<T>(
    path: string,
    validate: (value: unknown) => value is T,
    options: RequestOptions,
  ): Promise<ApiResult<T>> {
    const controller = new AbortController();
    let timedOut = false;
    const abort = () => controller.abort();
    options.signal?.addEventListener("abort", abort, { once: true });
    if (options.signal?.aborted) controller.abort();
    const timer = setTimeout(
      () => {
        timedOut = true;
        controller.abort();
      },
      Math.min(options.timeoutMs ?? API_TIMEOUT_MS, API_TIMEOUT_MS),
    );
    try {
      if (controller.signal.aborted) return { ok: false, kind: "cancelled" };
      const query = options.query?.toString();
      const url = `${origin}${path}${query ? `?${query}` : ""}`;
      const response = await transport(url, {
        method: "GET",
        headers: { Accept: "application/json" },
        credentials: "omit",
        cache: "no-store",
        redirect: "error",
        signal: controller.signal,
      });
      if (!response.ok) return httpFailure(response.status);
      let value: unknown;
      try {
        value = await response.json();
      } catch (error) {
        if (controller.signal.aborted) throw error;
        return { ok: false, kind: "invalid_response" };
      }
      if (controller.signal.aborted)
        return { ok: false, kind: timedOut ? "timeout" : "cancelled" };
      return validate(value)
        ? { ok: true, data: value }
        : { ok: false, kind: "invalid_response" };
    } catch {
      return {
        ok: false,
        kind: timedOut
          ? "timeout"
          : options.signal?.aborted
            ? "cancelled"
            : "network",
      };
    } finally {
      clearTimeout(timer);
      options.signal?.removeEventListener("abort", abort);
    }
  }
  const listPath = "/api/v1/forms" satisfies keyof paths;
  return {
    listForms: (options: RequestOptions = {}) => read(listPath, forms, options),
    getForm: (
      id: components["schemas"]["FormSummary"]["id"],
      options: RequestOptions = {},
    ) =>
      publicId(id)
        ? read(`${listPath}/${encodeURIComponent(id)}`, detail, options)
        : Promise.resolve<ApiResult<FormDetail>>({
            ok: false,
            kind: "request",
          }),
  };
}
