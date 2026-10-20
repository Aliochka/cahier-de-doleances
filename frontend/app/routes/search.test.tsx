import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  createMemoryRouter,
  RouterContextProvider,
  RouterProvider,
} from "react-router";
import { beforeEach, expect, it, vi } from "vitest";
import { page } from "../features/search/fixtures.test-support";
import { SearchControls } from "../features/search/search-controls";
import { SearchResults } from "../features/search/search-results";
import { type SearchState, searchUrl } from "../features/search/search-url";
import { search } from "../lib/api.server";
import { loader } from "./search";

vi.mock("../lib/api.server", () => ({ search: vi.fn() }));
beforeEach(() => vi.resetAllMocks());
const state: SearchState = {
  q: page.q,
  cursor: page.first_cursor,
  page_size: 20,
};
const args = (query = "") => ({
  request: new Request(`http://localhost/recherche${query}`),
  url: new URL(`http://localhost/recherche${query}`),
  params: {},
  context: new RouterContextProvider(),
  pattern: "/recherche",
});
function renderPage(value = page) {
  return render(
    <RouterProvider
      router={createMemoryRouter([
        { path: "*", element: <SearchResults page={value} state={state} /> },
      ])}
    />,
  );
}
it.each(["", "?q=", "?q=+++"])(
  "accueil sans appel au moteur %s",
  async (query) => {
    const result = await loader(args(query));
    expect(result.init?.status).toBe(200);
    expect(result.data.result).toBeNull();
    expect(search).not.toHaveBeenCalled();
  },
);
it("fige la première page par une seule redirection et transmet le signal", async () => {
  vi.mocked(search).mockResolvedValue({ ok: true, data: page });
  const request = args(`?${new URLSearchParams({ q: page.q })}`);
  try {
    await loader(request);
    throw new Error("redirection attendue");
  } catch (response) {
    expect(response).toBeInstanceOf(Response);
    const redirect = response as Response;
    expect(redirect.status).toBe(303);
    expect(redirect.headers.get("Location")).toBe(searchUrl(state));
    expect(redirect.headers.get("Cache-Control")).toBe("private, no-store");
  }
  expect(search).toHaveBeenCalledExactlyOnceWith(
    { q: page.q, page_size: 20 },
    { signal: request.request.signal },
  );
  const stable = await loader(
    args(
      `?${new URLSearchParams({ q: page.q, cursor: page.first_cursor ?? "" })}`,
    ),
  );
  expect(stable.data.result).toEqual(page);
  expect(search).toHaveBeenCalledTimes(2);
});
it.each([
  "?q=a&q=b",
  "?tab=answers",
  "?cursor=",
  "?q=x&cursor=",
  "?q=x&question_id=42",
  "?q=x&page_size=21",
  `?q=${"x".repeat(513)}`,
])("validation sans appel API %s", async (query) => {
  const result = await loader(args(query));
  expect(result.init?.status).toBe(422);
  expect(search).not.toHaveBeenCalled();
});
it.each([
  ["expired", 410],
  ["application", 500],
  ["unavailable", 503],
  ["server_timeout", 504],
  ["invalid_response", 502],
  ["request", 422],
] as const)("statut SSR %s", async (kind, status) => {
  vi.mocked(search).mockResolvedValue({ ok: false, kind, status });
  const result = await loader(args("?q=exemple"));
  expect(result.init?.status).toBe(status);
  expect(result.data.result).toBeNull();
  expect(result.init?.headers).toMatchObject({
    "Cache-Control": "private, no-store",
    "X-Robots-Tag": "noindex, follow",
  });
});
it("conserve les textes, le contexte, les BIGINT et les champs Autre", () => {
  renderPage();
  const list = screen.getByRole("list", { name: "Réponses citoyennes" });
  expect(list.children).toHaveLength(20);
  expect(list.children[0]).toHaveTextContent("Première réponse");
  expect(list.children[1]).toHaveTextContent("Non");
  expect(screen.getByText("Autre A")).toBeVisible();
  expect(screen.getByText("Autre B")).toBeVisible();
  expect(list.querySelector("script")).toBeNull();
  expect(list.querySelector("blockquote p")?.textContent).toBe(
    page.items[0]?.texts[0]?.text,
  );
  expect(
    screen.getAllByRole("link", { name: "Lire la contribution complète" })[0],
  ).toHaveAttribute("href", page.items[0]?.url);
  expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(20);
  expect(screen.queryByText(/1 789|identifiant décroissant/)).toBeNull();
  expect(screen.queryByRole("tab")).toBeNull();
});
it("conserve les curseurs suivant, précédent et premier sans imposer de profondeur", () => {
  const current = {
    ...page,
    previous_cursor: "previous+2/=opaque",
    first_cursor: "first+1/=opaque",
    window: { ...page.window, document_limit: 1789, retrieval_depth: 1789 },
  };
  renderPage(current);
  for (const [label, cursor] of [
    ["Page suivante", page.next_cursor],
    ["Page précédente", current.previous_cursor],
    ["Première page", current.first_cursor],
  ] as const)
    expect(screen.getByRole("link", { name: label })).toHaveAttribute(
      "href",
      searchUrl({ ...state, cursor }),
    );
});
it("ne confond pas absence de résultat et sources retirées", () => {
  const empty = {
    ...page,
    state: "sources_unavailable" as const,
    items: [],
    warnings: [
      {
        code: "source_unavailable" as const,
        count: 1,
        message: "Message public",
      },
    ],
  };
  renderPage(empty);
  expect(screen.getByText(/ne sont plus consultables/)).toBeVisible();
  expect(screen.getByText(/retirées de cette sélection/)).toBeVisible();
  expect(screen.queryByText(/Aucun résultat pour cette recherche/)).toBeNull();
});
it("la saisie reste un formulaire GET sans recherche à la frappe et accessible", async () => {
  const change = vi.fn();
  render(
    <RouterProvider
      router={createMemoryRouter([
        {
          path: "*",
          element: (
            <SearchControls
              draft=""
              onDraftChange={change}
              error="512 caractères maximum."
            />
          ),
        },
      ])}
    />,
  );
  const input = screen.getByLabelText("Votre question ou votre sujet");
  await userEvent.type(input, "Pouvoir d’achat");
  expect(change).toHaveBeenCalled();
  expect(search).not.toHaveBeenCalled();
  expect(input).toHaveAttribute("aria-invalid", "true");
  expect(input).toHaveAccessibleDescription(/512 caractères/);
  expect(screen.getByRole("search")).toHaveAttribute("method", "get");
});
