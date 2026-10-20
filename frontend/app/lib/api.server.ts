import {
  type AnswerPage,
  type AnswersQuery,
  type ApiResult,
  type AuthorFormsPage,
  type AuthorFormsQuery,
  type ContributionDetail,
  createPublicApi,
  type FormDetail,
  type Forms,
  type HybridSearchPage,
  type HybridSearchQuery,
  type PublicAuthor,
  type QuestionDetail,
  type QuestionStatistics,
  type RequestOptions,
} from "./api";

function backendOrigin(): string | null {
  try {
    const value = process.env.API_BASE_URL;
    if (!value) return null;
    const url = new URL(value);
    const local = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
    const dockerBackend =
      url.protocol === "http:" && url.hostname === "app" && url.port === "8000";
    if (
      (url.protocol !== "https:" &&
        !(local && url.protocol === "http:") &&
        !dockerBackend) ||
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
function publicApi(origin: string) {
  if (origin !== "http://app:8000") return createPublicApi(origin);
  const transport: typeof fetch = (input, init) =>
    fetch(input, {
      ...init,
      headers: {
        ...Object.fromEntries(new Headers(init?.headers).entries()),
        "x-forwarded-proto": "https",
      },
    });
  return createPublicApi(origin, transport);
}
// Read configuration only when a loader calls the API, never during build.
export function listForms(
  options: RequestOptions = {},
): Promise<ApiResult<Forms>> {
  const origin = backendOrigin();
  return origin
    ? publicApi(origin).listForms(options)
    : Promise.resolve({ ok: false, kind: "configuration" });
}
export function getForm(
  id: string,
  options: RequestOptions = {},
): Promise<ApiResult<FormDetail>> {
  const origin = backendOrigin();
  return origin
    ? publicApi(origin).getForm(id, options)
    : Promise.resolve({ ok: false, kind: "configuration" });
}

export function getQuestion(
  id: string,
  options: RequestOptions = {},
): Promise<ApiResult<QuestionDetail>> {
  const origin = backendOrigin();
  return origin
    ? publicApi(origin).getQuestion(id, options)
    : Promise.resolve({ ok: false, kind: "configuration" });
}
export function getQuestionAnswers(
  id: string,
  query: AnswersQuery = {},
  options: RequestOptions = {},
): Promise<ApiResult<AnswerPage>> {
  const origin = backendOrigin();
  return origin
    ? publicApi(origin).getQuestionAnswers(id, query, options)
    : Promise.resolve({
        ok: false,
        kind: "configuration",
      });
}
export function getQuestionStats(
  id: string,
  options: RequestOptions = {},
): Promise<ApiResult<QuestionStatistics>> {
  const origin = backendOrigin();
  return origin
    ? publicApi(origin).getQuestionStats(id, options)
    : Promise.resolve({ ok: false, kind: "configuration" });
}

export function getAuthor(
  id: string,
  options: RequestOptions = {},
): Promise<ApiResult<PublicAuthor>> {
  const origin = backendOrigin();
  return origin
    ? publicApi(origin).getAuthor(id, options)
    : Promise.resolve({ ok: false, kind: "configuration" });
}
export function getAuthorForms(
  id: string,
  query: AuthorFormsQuery = {},
  options: RequestOptions = {},
): Promise<ApiResult<AuthorFormsPage>> {
  const origin = backendOrigin();
  return origin
    ? publicApi(origin).getAuthorForms(id, query, options)
    : Promise.resolve({ ok: false, kind: "configuration" });
}
export function getContribution(
  formId: string,
  id: string,
  options: RequestOptions = {},
): Promise<ApiResult<ContributionDetail>> {
  const origin = backendOrigin();
  return origin
    ? publicApi(origin).getContribution(formId, id, options)
    : Promise.resolve({ ok: false, kind: "configuration" });
}

export function search(
  query: HybridSearchQuery = {},
  options: RequestOptions = {},
): Promise<ApiResult<HybridSearchPage>> {
  const origin = backendOrigin();
  return origin
    ? publicApi(origin).search(query, options)
    : Promise.resolve({ ok: false, kind: "configuration" });
}

export function getFormContribution(
  formId: string,
  index = "1",
  options: RequestOptions = {},
): Promise<ApiResult<ContributionDetail>> {
  const origin = backendOrigin();
  return origin
    ? publicApi(origin).getFormContribution(formId, index, options)
    : Promise.resolve({ ok: false, kind: "configuration" });
}
