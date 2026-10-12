import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import {
  createMemoryRouter,
  RouterContextProvider,
  RouterProvider,
} from "react-router";
import { beforeEach, expect, it, vi } from "vitest";
import { answers, catalog } from "../features/search/fixtures.test-support";
import { SearchControls } from "../features/search/search-controls";
import { SearchResults } from "../features/search/search-results";
import { type SearchState, searchUrl } from "../features/search/search-url";
import { searchAnswers, searchCatalog } from "../lib/api.server";
import { loader } from "./search";

vi.mock("../lib/api.server", () => ({
  searchAnswers: vi.fn(),
  searchCatalog: vi.fn(),
}));
beforeEach(() => vi.resetAllMocks());
function renderControls(element: ReactNode) {
  return render(
    <RouterProvider router={createMemoryRouter([{ path: "*", element }])} />,
  );
}
const state: SearchState = {
  q: answers.q,
  tab: "answers",
  cursor: null,
  cursor_forms: null,
  cursor_questions: null,
};
const args = (query = "") => ({
  request: new Request(`http://localhost/recherche${query}`),
  url: new URL(`http://localhost/recherche${query}`),
  params: {},
  context: new RouterContextProvider(),
  pattern: "/recherche",
});

it.each(["", "?q=", "?q=+++"])(
  "ne recherche pas un terme vide %s",
  async (query) => {
    const result = await loader(args(query));
    expect(result.init?.status).toBe(200);
    expect(result.data.result).toBeNull();
    expect(searchAnswers).not.toHaveBeenCalled();
    expect(searchCatalog).not.toHaveBeenCalled();
  },
);
it("charge seulement les réponses par défaut et transmet le signal et le curseur intact", async () => {
  vi.mocked(searchAnswers).mockResolvedValue({ ok: true, data: answers });
  const input = args(
    `?${new URLSearchParams({ q: ` ${answers.q} `, cursor: "page+2/=opaque", cursor_forms: "ignored" })}`,
  );
  const response = await loader(input);
  expect(searchAnswers).toHaveBeenCalledExactlyOnceWith(
    { q: answers.q, cursor: "page+2/=opaque" },
    { signal: input.request.signal },
  );
  expect(searchCatalog).not.toHaveBeenCalled();
  expect(response.data.result).toEqual({ type: "answers", page: answers });
  expect(response.init?.headers).toEqual({
    "Cache-Control": "private, no-store",
    "X-Robots-Tag": "noindex, follow",
  });
});
it("charge seulement le catalogue et ses deux curseurs sans taille arbitraire", async () => {
  vi.mocked(searchCatalog).mockResolvedValue({ ok: true, data: catalog });
  const input = args(
    `?${new URLSearchParams({ q: answers.q, tab: "catalog", cursor_forms: "forms+2/=opaque", cursor_questions: "questions+2/=opaque", cursor: "ignored" })}`,
  );
  const response = await loader(input);
  expect(searchCatalog).toHaveBeenCalledExactlyOnceWith(
    {
      q: answers.q,
      cursor_forms: "forms+2/=opaque",
      cursor_questions: "questions+2/=opaque",
    },
    { signal: input.request.signal },
  );
  expect(searchAnswers).not.toHaveBeenCalled();
  expect(response.data.result).toEqual({ type: "catalog", page: catalog });
});
it.each([
  `?q=${"x".repeat(513)}`,
  "?q=a&q=b",
  "?tab=inconnu",
  "?cursor=",
  "?tab=catalog&cursor_forms=",
  `?cursor=${"x".repeat(1025)}`,
  "?cursor=a&cursor=b",
  "?tab=catalog&cursor_questions=a&cursor_questions=b",
])("rejette les paramètres invalides sans appel API %s", async (query) => {
  const response = await loader(args(query));
  expect(response.init?.status).toBe(422);
  expect(response.data.failure?.kind).toBe("request");
  expect(searchAnswers).not.toHaveBeenCalled();
  expect(searchCatalog).not.toHaveBeenCalled();
});
it.each([
  ["request", 422],
  ["application", 500],
  ["unavailable", 503],
  ["server_timeout", 504],
  ["timeout", 504],
  ["invalid_response", 502],
  ["network", 503],
] as const)("préserve %s et le vrai statut %i", async (kind, status) => {
  vi.mocked(searchAnswers).mockResolvedValue({ ok: false, kind });
  const response = await loader(args("?q=exemple"));
  expect(response.init?.status).toBe(status);
  expect(response.init?.headers).toEqual({
    "Cache-Control": "private, no-store",
    "X-Robots-Tag": "noindex, nofollow",
  });
  expect(response.data.result).toBeNull();
});
it("un résultat vide est un succès HTTP 200", async () => {
  vi.mocked(searchAnswers).mockResolvedValue({
    ok: true,
    data: { ...answers, items: [], has_next: false, next_cursor: null },
  });
  const response = await loader(args("?q=absent"));
  expect(response.init?.status).toBe(200);
  renderControls(
    <SearchResults
      result={{
        type: "answers",
        page: { ...answers, items: [], has_next: false, next_cursor: null },
      }}
      state={state}
    />,
  );
  expect(screen.getByText(/Aucun résultat pour cette recherche/)).toBeVisible();
  expect(screen.queryByRole("link", { name: "Résultats suivants" })).toBeNull();
});
it("préserve l'ordre, les BIGINT, les paragraphes et la confidentialité des liens auteur", () => {
  renderControls(
    <SearchResults result={{ type: "answers", page: answers }} state={state} />,
  );
  const list = screen.getByRole("list", { name: "Résultats Réponses" });
  expect(list.children[0]).toHaveTextContent("Première réponse");
  expect(list.children[1]).toHaveTextContent("Seconde réponse");
  expect(
    screen.getByRole("link", { name: "Pseudonyme public" }),
  ).toHaveAttribute("href", "/authors/9007199254743994");
  expect(screen.queryByRole("link", { name: "Auteur anonyme" })).toBeNull();
  expect(
    screen.getAllByRole("link", { name: "Voir la contribution complète" })[0],
  ).toHaveAttribute("href", answers.items[0]?.url);
  expect(list.querySelector("script")).toBeNull();
  expect(list.querySelector("article p:nth-of-type(3)")?.textContent).toBe(
    answers.items[0]?.text,
  );
  expect(
    screen.getByRole("link", { name: "Résultats suivants" }),
  ).toHaveAttribute(
    "href",
    searchUrl({ ...state, cursor: answers.next_cursor }),
  );
  expect(screen.getByText(/1 789 candidats/)).toBeVisible();
});
it("distingue les catégories sans tri ni slug recalculé et pagine indépendamment", () => {
  const current = {
    ...state,
    tab: "catalog" as const,
    cursor_forms: "form-current",
    cursor_questions: "question-current",
  };
  renderControls(
    <SearchResults
      result={{ type: "catalog", page: catalog }}
      state={current}
    />,
  );
  expect(
    screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent),
  ).toEqual([
    ...catalog.forms.map((f) => f.name),
    ...catalog.questions.map((q) => q.prompt),
  ]);
  expect(
    screen.getByRole("link", { name: catalog.questions[0]?.prompt }),
  ).toHaveAttribute("href", catalog.questions[0]?.url);
  for (const [label, key, cursor, preserved] of [
    [
      "Enquêtes suivantes",
      "cursor_forms",
      catalog.next_cursor_forms,
      "cursor_questions",
    ],
    [
      "Questions suivantes",
      "cursor_questions",
      catalog.next_cursor_questions,
      "cursor_forms",
    ],
  ] as const) {
    const url = new URL(
      screen.getByRole("link", { name: label }).getAttribute("href") ?? "",
      "http://localhost",
    );
    expect(url.searchParams.get(key)).toBe(cursor);
    expect(url.searchParams.get(preserved)).toBe(current[preserved]);
    expect(url.searchParams.has("cursor")).toBe(false);
  }
  expect(screen.queryByText(/1 789/)).toBeNull();
});
it("les liens de catégories gardent le terme soumis et effacent tous les curseurs", () => {
  renderControls(
    <SearchControls
      state={{ ...state, cursor: "old", cursor_forms: "old-form" }}
      draft="Autre brouillon"
      onDraftChange={vi.fn()}
    />,
  );
  expect(screen.getByLabelText("Mots-clés")).toHaveValue("Autre brouillon");
  expect(screen.getByRole("link", { name: /^Réponses$/ })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(
    screen.getByRole("link", { name: "Questions et enquêtes" }),
  ).toHaveAttribute("href", searchUrl({ q: state.q, tab: "catalog" }));
  expect(screen.queryByRole("tab")).toBeNull();
});
it("la saisie ne déclenche aucune recherche et l'erreur est associée au champ", async () => {
  const change = vi.fn();
  renderControls(
    <SearchControls
      state={state}
      draft=""
      onDraftChange={change}
      error="La recherche est limitée à 512 caractères."
    />,
  );
  await userEvent.type(screen.getByLabelText("Mots-clés"), "école & lecture");
  expect(change).toHaveBeenCalled();
  expect(searchAnswers).not.toHaveBeenCalled();
  expect(searchCatalog).not.toHaveBeenCalled();
  expect(screen.getByLabelText("Mots-clés")).toHaveAccessibleDescription(
    /512 caractères/,
  );
  expect(screen.getByLabelText("Mots-clés")).toHaveAttribute(
    "aria-invalid",
    "true",
  );
  expect(screen.getByLabelText("Mots-clés")).toHaveAttribute(
    "maxlength",
    "512",
  );
});
