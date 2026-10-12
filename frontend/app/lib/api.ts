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
export type QuestionDetail = components["schemas"]["QuestionDetail"];
export type AnswerPage = components["schemas"]["AnswerPage"];
export type QuestionStatistics = components["schemas"]["QuestionStatistics"];
export type AnswersQuery = NonNullable<
  operations["list_public_question_answers"]["parameters"]["query"]
>;
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
function formQuestion(
  value: unknown,
): value is components["schemas"]["FormQuestion"] {
  return (
    record(value) &&
    publicId(value.id) &&
    publicId(value.form_id) &&
    typeof value.prompt === "string" &&
    typeof value.type === "string" &&
    (value.position === null ||
      (typeof value.position === "number" &&
        Number.isInteger(value.position))) &&
    typeof value.slug === "string" &&
    typeof value.url === "string"
  );
}
function detail(value: unknown): value is FormDetail {
  if (!record(value)) return false;
  const questions = value.questions;
  return (
    summary(value) && Array.isArray(questions) && questions.every(formQuestion)
  );
}
function question(value: unknown): value is QuestionDetail {
  if (!record(value)) return false;
  const { display_mode, form } = value;
  return (
    formQuestion(value) &&
    (display_mode === "text" || display_mode === "choice") &&
    record(form) &&
    publicId(form.id) &&
    typeof form.name === "string" &&
    typeof form.url === "string"
  );
}
function answerPage(value: unknown): value is AnswerPage {
  return (
    record(value) &&
    publicId(value.question_id) &&
    typeof value.page_size === "number" &&
    Number.isInteger(value.page_size) &&
    value.page_size >= 1 &&
    value.page_size <= 100 &&
    typeof value.has_next === "boolean" &&
    (value.next_cursor === null || typeof value.next_cursor === "string") &&
    (!value.has_next || typeof value.next_cursor === "string") &&
    Array.isArray(value.items) &&
    value.items.every(
      (a: unknown) =>
        record(a) &&
        publicId(a.id) &&
        publicId(a.question_id) &&
        publicId(a.contribution_id) &&
        typeof a.text === "string" &&
        typeof a.is_truncated === "boolean" &&
        typeof a.url === "string" &&
        (a.submitted_at === null ||
          (typeof a.submitted_at === "string" &&
            !Number.isNaN(Date.parse(a.submitted_at)))) &&
        (a.author === null ||
          (record(a.author) &&
            publicId(a.author.id) &&
            typeof a.author.name === "string" &&
            typeof a.author.is_anonymous === "boolean" &&
            typeof a.author.slug === "string" &&
            typeof a.author.url === "string")),
    )
  );
}
function statistics(value: unknown): value is QuestionStatistics {
  return (
    record(value) &&
    publicId(value.question_id) &&
    (value.type === "single_choice" || value.type === "multi_choice") &&
    value.percentage_denominator === "total_answers" &&
    value.percentage_decimal_places === 2 &&
    [
      value.total_answers,
      value.answered_contributions_count,
      value.total_selections,
      value.total_option_selections,
      value.other_text_answers_count,
    ].every((v) => typeof v === "number" && Number.isInteger(v) && v >= 0) &&
    Array.isArray(value.categories) &&
    value.categories.every(
      (c: unknown) =>
        record(c) &&
        (c.option_id === null || publicId(c.option_id)) &&
        (c.kind === "option" || c.kind === "other_text") &&
        typeof c.label === "string" &&
        typeof c.count === "number" &&
        Number.isInteger(c.count) &&
        c.count >= 0 &&
        typeof c.percentage === "number" &&
        Number.isFinite(c.percentage) &&
        c.percentage >= 0 &&
        (c.position === null ||
          (typeof c.position === "number" && Number.isInteger(c.position))),
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
  const questionPath = "/api/v1/questions/{question_id}" satisfies keyof paths;
  const pathFor = (id: string) =>
    questionPath.replace("{question_id}", encodeURIComponent(id));
  return {
    getQuestion: (id: QuestionDetail["id"], options: RequestOptions = {}) =>
      publicId(id)
        ? read(pathFor(id), question, options)
        : Promise.resolve<ApiResult<QuestionDetail>>({
            ok: false,
            kind: "request",
          }),
    getQuestionAnswers: (
      id: QuestionDetail["id"],
      query: AnswersQuery = {},
      options: RequestOptions = {},
    ) => {
      const params = new URLSearchParams();
      if (query.cursor !== undefined && query.cursor !== null)
        params.set("cursor", query.cursor);
      if (query.page_size !== undefined)
        params.set("page_size", String(query.page_size));
      return publicId(id)
        ? read(`${pathFor(id)}/answers`, answerPage, {
            ...options,
            query: params,
          })
        : Promise.resolve<ApiResult<AnswerPage>>({
            ok: false,
            kind: "request",
          });
    },
    getQuestionStats: (
      id: QuestionDetail["id"],
      options: RequestOptions = {},
    ) =>
      publicId(id)
        ? read(`${pathFor(id)}/stats`, statistics, options)
        : Promise.resolve<ApiResult<QuestionStatistics>>({
            ok: false,
            kind: "request",
          }),
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
