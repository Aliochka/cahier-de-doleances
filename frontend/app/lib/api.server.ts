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

export function getQuestion(
  id: string,
  options: RequestOptions = {},
): Promise<ApiResult<QuestionDetail>> {
  const origin = backendOrigin();
  return origin
    ? createPublicApi(origin).getQuestion(id, options)
    : Promise.resolve({ ok: false, kind: "configuration" });
}
export function getQuestionAnswers(
  id: string,
  query: AnswersQuery = {},
  options: RequestOptions = {},
): Promise<ApiResult<AnswerPage>> {
  const origin = backendOrigin();
  return origin
    ? createPublicApi(origin).getQuestionAnswers(id, query, options)
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
    ? createPublicApi(origin).getQuestionStats(id, options)
    : Promise.resolve({ ok: false, kind: "configuration" });
}

export function getAuthor(
  id: string,
  options: RequestOptions = {},
): Promise<ApiResult<PublicAuthor>> {
  const origin = backendOrigin();
  return origin
    ? createPublicApi(origin).getAuthor(id, options)
    : Promise.resolve({ ok: false, kind: "configuration" });
}
export function getAuthorForms(
  id: string,
  query: AuthorFormsQuery = {},
  options: RequestOptions = {},
): Promise<ApiResult<AuthorFormsPage>> {
  const origin = backendOrigin();
  return origin
    ? createPublicApi(origin).getAuthorForms(id, query, options)
    : Promise.resolve({ ok: false, kind: "configuration" });
}
export function getContribution(
  formId: string,
  id: string,
  options: RequestOptions = {},
): Promise<ApiResult<ContributionDetail>> {
  const origin = backendOrigin();
  return origin
    ? createPublicApi(origin).getContribution(formId, id, options)
    : Promise.resolve({ ok: false, kind: "configuration" });
}
