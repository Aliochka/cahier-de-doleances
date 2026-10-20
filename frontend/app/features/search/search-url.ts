export type SearchState = {
  q: string;
  cursor: string | null;
  page_size: number;
};

export function searchUrl(
  state: Pick<SearchState, "q"> & Partial<SearchState>,
): string {
  const query = new URLSearchParams({ q: state.q });
  if (state.page_size !== undefined && state.page_size !== 20)
    query.set("page_size", String(state.page_size));
  if (state.cursor) query.set("cursor", state.cursor);
  return `/recherche?${query}`;
}
