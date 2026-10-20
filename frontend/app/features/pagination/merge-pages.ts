import type {
  AnswerPage,
  AuthorFormsPage,
  HybridSearchPage,
} from "../../lib/api";

const unique = <T>(values: T[], key: (value: T) => string) => [
  ...new Map(values.map((value) => [key(value), value])).values(),
];
export const answerIds = (page: AnswerPage) =>
  page.items.map((item) => item.id);
export const searchIds = (page: HybridSearchPage) =>
  page.items.map((item) => item.answer_id);
export const authorIds = (page: AuthorFormsPage) =>
  page.forms.flatMap((form) => form.contributions.map((item) => item.id));
export function mergeAnswers(pages: AnswerPage[]): AnswerPage {
  const last = pages.at(-1);
  if (!last) throw new Error("Missing answer page");
  return {
    ...last,
    items: unique(
      pages.flatMap((page) => page.items),
      (item) => item.id,
    ),
  };
}
export function mergeSearch(pages: HybridSearchPage[]): HybridSearchPage {
  const last = pages.at(-1);
  if (!last) throw new Error("Missing search page");
  const items = unique(
    pages.flatMap((page) => page.items),
    (item) => item.answer_id,
  );
  return {
    ...last,
    items,
    state: items.length ? "results" : last.state,
    warnings: unique(
      pages.flatMap((page) => page.warnings),
      (value) => JSON.stringify(value),
    ),
  };
}
export function mergeAuthors(pages: AuthorFormsPage[]): AuthorFormsPage {
  const last = pages.at(-1);
  if (!last) throw new Error("Missing author page");
  const forms = new Map<string, AuthorFormsPage["forms"][number]>();
  for (const page of pages)
    for (const form of page.forms) {
      const existing = forms.get(form.id);
      forms.set(form.id, {
        ...form,
        contributions: unique(
          [...(existing?.contributions ?? []), ...form.contributions],
          (item) => item.id,
        ),
      });
    }
  return { ...last, forms: [...forms.values()] };
}
