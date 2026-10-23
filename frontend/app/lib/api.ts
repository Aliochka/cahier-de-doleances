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
  | "expired"
  | "application"
  | "unavailable"
  | "server_timeout"
  | "timeout"
  | "network"
  | "cancelled"
  | "invalid_response"
  | "configuration";
export type ApiFailure = {
  ok: false;
  kind: ApiErrorKind;
  status?: number;
  code?: HybridErrorCode;
};
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
export type PublicAuthor = components["schemas"]["PublicAuthor"];
export type AuthorFormsPage = components["schemas"]["AuthorFormsPage"];
export type ContributionDetail = components["schemas"]["ContributionDetail"];
export type AuthorFormsQuery = NonNullable<
  operations["list_public_author_forms"]["parameters"]["query"]
>;
export type HybridSearchPage = components["schemas"]["HybridSearchPage"];
export type HybridSearchQuery = NonNullable<
  operations["search_public_hybrid"]["parameters"]["query"]
>;
export type HybridErrorCode =
  | "invalid_query"
  | "invalid_cursor"
  | "search_expired"
  | "search_not_ready"
  | "search_unavailable"
  | "search_metadata_unavailable"
  | "search_busy"
  | "search_timeout"
  | "search_encoding_timeout"
  | "search_sql_timeout"
  | "search_metadata_timeout"
  | "search_cancelled"
  | "search_internal_error";
const searchErrorCodes = new Set<string>([
  "invalid_query",
  "invalid_cursor",
  "search_expired",
  "search_not_ready",
  "search_unavailable",
  "search_metadata_unavailable",
  "search_busy",
  "search_timeout",
  "search_encoding_timeout",
  "search_sql_timeout",
  "search_metadata_timeout",
  "search_cancelled",
  "search_internal_error",
]);
type FormSummary = components["schemas"]["FormSummary"];

export function httpFailure(status: number): ApiFailure {
  const kind =
    status === 410
      ? "expired"
      : status === 400 || status === 422
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
  if (!record(value) || !record(value.statistics_availability)) return false;
  const { questions, id } = value;
  const availability = value.statistics_availability;
  if (!["available", "unavailable"].includes(String(availability.status)))
    return false;
  const available = availability.status === "available";
  if (
    available &&
    (typeof availability.generation_id !== "string" ||
      typeof availability.calculated_at !== "string" ||
      !date(availability.calculated_at) ||
      typeof availability.method_version !== "string")
  )
    return false;
  return (
    summary(value) &&
    Array.isArray(questions) &&
    questions.every((entry: unknown) => {
      if (!record(entry)) return false;
      const { answers_count, statistics: choice } = entry;
      if (!formQuestion(entry) || entry.form_id !== id) return false;
      if (!available)
        return (
          (answers_count === undefined || answers_count === null) &&
          (choice === undefined || choice === null)
        );
      return (
        typeof answers_count === "number" &&
        Number.isSafeInteger(answers_count) &&
        answers_count >= 0 &&
        (["single_choice", "multi_choice"].includes(entry.type)
          ? statistics(choice) &&
            choice.question_id === entry.id &&
            choice.total_answers === answers_count
          : choice === null)
      );
    })
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
function date(value: unknown): boolean {
  return (
    value === null ||
    (typeof value === "string" && !Number.isNaN(Date.parse(value)))
  );
}
function author(value: unknown): value is PublicAuthor {
  return (
    record(value) &&
    publicId(value.id) &&
    typeof value.name === "string" &&
    typeof value.is_anonymous === "boolean" &&
    typeof value.slug === "string" &&
    typeof value.url === "string"
  );
}
function reference(
  value: unknown,
): value is components["schemas"]["ContributionReference"] {
  return (
    record(value) &&
    publicId(value.id) &&
    date(value.submitted_at) &&
    typeof value.api_url === "string"
  );
}
function formContext(
  value: unknown,
): value is components["schemas"]["QuestionForm"] {
  return (
    record(value) &&
    publicId(value.id) &&
    typeof value.name === "string" &&
    typeof value.url === "string"
  );
}
function authorForms(value: unknown): value is AuthorFormsPage {
  return (
    record(value) &&
    publicId(value.author_id) &&
    typeof value.has_next === "boolean" &&
    typeof value.page_size === "number" &&
    Number.isInteger(value.page_size) &&
    value.page_size >= 1 &&
    value.page_size <= 100 &&
    (value.next_after_id === null || publicId(value.next_after_id)) &&
    (!value.has_next || publicId(value.next_after_id)) &&
    Array.isArray(value.forms) &&
    value.forms.every(
      (f: unknown) =>
        record(f) &&
        Array.isArray(f.contributions) &&
        f.contributions.every(reference) &&
        formContext(f),
    )
  );
}
function contribution(value: unknown): value is ContributionDetail {
  if (!record(value) || !formContext(value.form)) return false;
  const formId = value.form.id;
  if (!reference(value.contribution)) return false;
  const contributionId = value.contribution.id;
  return (
    [value.previous_id, value.next_id].every(
      (id) =>
        id === undefined ||
        id === null ||
        (publicId(id) && id !== contributionId),
    ) &&
    (value.previous_id == null ||
      value.next_id == null ||
      value.previous_id !== value.next_id) &&
    (value.author === null || author(value.author)) &&
    (value.legacy_index === null ||
      value.legacy_index === undefined ||
      publicId(value.legacy_index)) &&
    Array.isArray(value.answers) &&
    new Set(value.answers.map((a: unknown) => (record(a) ? a.id : undefined)))
      .size === value.answers.length &&
    value.answers.every(
      (a: unknown) =>
        record(a) &&
        publicId(a.id) &&
        formQuestion(a.question) &&
        a.question.form_id === formId &&
        (a.position === null ||
          (typeof a.position === "number" && Number.isInteger(a.position))) &&
        (a.text === null || typeof a.text === "string") &&
        (a.value === null || typeof a.value === "string") &&
        Array.isArray(a.other_text) &&
        a.other_text.every((v: unknown) => typeof v === "string") &&
        Array.isArray(a.selected_options) &&
        a.selected_options.every(
          (o: unknown) =>
            record(o) &&
            publicId(o.id) &&
            typeof o.label === "string" &&
            (o.position === null ||
              (typeof o.position === "number" && Number.isInteger(o.position))),
        ),
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

function continuation(hasNext: unknown, cursor: unknown): boolean {
  return (
    typeof hasNext === "boolean" &&
    (cursor === null || typeof cursor === "string") &&
    (!hasNext ||
      (typeof cursor === "string" &&
        cursor.length > 0 &&
        cursor.length <= 1024))
  );
}
function positive(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value > 0;
}
function opaque(value: unknown): boolean {
  return (
    value === null ||
    (typeof value === "string" && value.length > 0 && value.length <= 1024)
  );
}
function hybridSearch(value: unknown): value is HybridSearchPage {
  if (!record(value) || !Array.isArray(value.items) || !record(value.window))
    return false;
  return (
    typeof value.q === "string" &&
    value.mode === "hybrid" &&
    ["idle", "results", "empty", "sources_unavailable"].includes(
      String(value.state),
    ) &&
    typeof value.recipe_version === "string" &&
    positive(value.page_size) &&
    value.page_size <= 20 &&
    value.items.length <= value.page_size &&
    continuation(value.has_next, value.next_cursor) &&
    opaque(value.previous_cursor) &&
    opaque(value.first_cursor) &&
    date(value.expires_at) &&
    positive(value.window.document_limit) &&
    positive(value.window.retrieval_depth) &&
    typeof value.window.answer_count === "number" &&
    Number.isSafeInteger(value.window.answer_count) &&
    value.window.answer_count >= value.items.length &&
    value.window.exhaustive === false &&
    new Set(
      value.items.map((item: unknown) =>
        record(item) ? item.answer_id : undefined,
      ),
    ).size === value.items.length &&
    value.items.every(
      (item: unknown) =>
        record(item) &&
        publicId(item.answer_id) &&
        publicId(item.contribution_id) &&
        positive(item.rank) &&
        typeof item.is_truncated === "boolean" &&
        record(item.question) &&
        publicId(item.question.id) &&
        typeof item.question.prompt === "string" &&
        typeof item.question.url === "string" &&
        item.question.url.startsWith(`/questions/${item.question.id}-`) &&
        record(item.form) &&
        publicId(item.form.id) &&
        typeof item.form.name === "string" &&
        item.form.url === `/forms/${item.form.id}` &&
        item.url ===
          `/forms/${item.form.id}/contributions/${item.contribution_id}#answer-${item.answer_id}` &&
        Array.isArray(item.texts) &&
        item.texts.length > 0 &&
        item.texts.every(
          (unit: unknown) =>
            record(unit) &&
            ["open_answer", "other_text"].includes(String(unit.unit_type)) &&
            typeof unit.unit_index === "number" &&
            Number.isSafeInteger(unit.unit_index) &&
            unit.unit_index >= 0 &&
            typeof unit.text === "string",
        ),
    ) &&
    Array.isArray(value.warnings) &&
    value.warnings.every(
      (warning: unknown) =>
        record(warning) &&
        warning.code === "source_unavailable" &&
        positive(warning.count) &&
        typeof warning.message === "string",
    )
  );
}

/** Read-only public transport. It never forwards account cookies or API error bodies. */
export function createPublicApi(origin = "", transport: typeof fetch = fetch) {
  async function read<T>(
    path: string,
    validate: (value: unknown) => value is T,
    options: RequestOptions,
    structuredErrors = false,
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
      if (!response.ok) {
        const failure = httpFailure(response.status);
        if (structuredErrors) {
          try {
            const body: unknown = await response.json();
            if (
              record(body) &&
              record(body.error) &&
              typeof body.error.code === "string" &&
              searchErrorCodes.has(body.error.code)
            )
              return { ...failure, code: body.error.code as HybridErrorCode };
          } catch (error) {
            if (controller.signal.aborted) throw error;
          }
        }
        return failure;
      }
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
  const authorPath = "/api/v1/authors/{author_id}" satisfies keyof paths;
  const contributionPath =
    "/api/v1/forms/{form_id}/contributions/{contribution_id}" satisfies keyof paths;
  const searchPath = "/api/v1/search" satisfies keyof paths;
  return {
    search: (query: HybridSearchQuery = {}, options: RequestOptions = {}) => {
      const params = new URLSearchParams();
      if (query.q !== undefined) params.set("q", query.q);
      if (query.cursor !== undefined && query.cursor !== null)
        params.set("cursor", query.cursor);
      if (query.page_size !== undefined)
        params.set("page_size", String(query.page_size));
      return read(
        searchPath,
        hybridSearch,
        { ...options, query: params },
        true,
      );
    },
    getAuthor: (id: string, options: RequestOptions = {}) =>
      publicId(id)
        ? read(
            authorPath.replace("{author_id}", encodeURIComponent(id)),
            author,
            options,
          )
        : Promise.resolve<ApiResult<PublicAuthor>>({
            ok: false,
            kind: "request",
          }),
    getAuthorForms: (
      id: string,
      query: AuthorFormsQuery = {},
      options: RequestOptions = {},
    ) => {
      const params = new URLSearchParams();
      if (query.after_id !== undefined && query.after_id !== null)
        params.set("after_id", query.after_id);
      if (query.page_size !== undefined)
        params.set("page_size", String(query.page_size));
      return publicId(id)
        ? read(
            `${authorPath.replace("{author_id}", encodeURIComponent(id))}/forms`,
            authorForms,
            { ...options, query: params },
          )
        : Promise.resolve<ApiResult<AuthorFormsPage>>({
            ok: false,
            kind: "request",
          });
    },
    getFormContribution: (
      formId: string,
      index = "1",
      options: RequestOptions = {},
    ) =>
      publicId(formId) && publicId(index)
        ? read(
            `/api/v1/forms/${encodeURIComponent(formId)}/contributions`,
            contribution,
            { ...options, query: new URLSearchParams({ contrib: index }) },
          )
        : Promise.resolve<ApiResult<ContributionDetail>>({
            ok: false,
            kind: "request",
          }),
    getContribution: (
      formId: string,
      id: string,
      options: RequestOptions = {},
    ) =>
      publicId(formId) && publicId(id)
        ? read(
            contributionPath
              .replace("{form_id}", encodeURIComponent(formId))
              .replace("{contribution_id}", encodeURIComponent(id)),
            contribution,
            options,
          )
        : Promise.resolve<ApiResult<ContributionDetail>>({
            ok: false,
            kind: "request",
          }),
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
      if (query.other_only !== undefined)
        params.set("other_only", String(query.other_only));
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
