export type SearchTab = "answers" | "catalog";
export type SearchState = {
  q: string;
  tab: SearchTab;
  cursor: string | null;
  cursor_forms: string | null;
  cursor_questions: string | null;
};
export function searchUrl(
  state: Pick<SearchState, "q" | "tab"> & Partial<SearchState>,
): string {
  const query = new URLSearchParams({ q: state.q, tab: state.tab });
  if (state.tab === "answers" && state.cursor)
    query.set("cursor", state.cursor);
  if (state.tab === "catalog") {
    if (state.cursor_forms) query.set("cursor_forms", state.cursor_forms);
    if (state.cursor_questions)
      query.set("cursor_questions", state.cursor_questions);
  }
  return `/recherche?${query}`;
}
