import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, MemoryRouter, RouterProvider } from "react-router";
import { expect, it } from "vitest";
import { isHistoricalResult } from "../../lib/api";
import { mergeSearch, searchIds } from "../pagination/merge-pages";
import { page } from "../search/fixtures.test-support";
import { SearchControls } from "../search/search-controls";
import { searchUrl } from "../search/search-url";
import { historical } from "./fixtures.test-support";
import { HistoricalCard } from "./historical-card";

it("présente le cahier comme document et conserve le lien versionné au passage", () => {
  render(
    <MemoryRouter>
      <ol>
        <HistoricalCard item={historical} />
      </ol>
    </MemoryRouter>,
  );
  expect(screen.getByRole("heading", { name: historical.title })).toBeVisible();
  expect(
    screen.getByRole("link", { name: /Lire le cahier intégral/ }),
  ).toHaveAttribute("href", historical.url);
  const warning = historical.warnings[0];
  if (!warning) throw new Error("Missing warning fixture");
  expect(screen.getByText(warning.message)).toBeVisible();
  expect(document.querySelector("script")).toBeNull();
  expect(screen.getByText(/sans HTML/)).toHaveTextContent(
    "<script>sans HTML</script>",
  );
});
it("dédoublonne les cahiers sans perdre les réponses distinctes et leurs types", () => {
  const a = page.items[0],
    b = page.items[1];
  if (!a || !b) throw new Error("Missing response fixtures");
  const first = { ...page, items: [historical, a] };
  const merged = mergeSearch([first, { ...first, items: [historical, b] }]);
  expect(searchIds(merged)).toEqual([
    `1789:${historical.document_id}`,
    a.answer_id,
    b.answer_id,
  ]);
  expect(merged.items.filter(isHistoricalResult)).toHaveLength(1);
});
it("conserve le corpus dans les liens et abandonne le curseur lors d’un changement", async () => {
  const user = userEvent.setup();
  const router = createMemoryRouter(
    [
      {
        path: "/recherche",
        element: (
          <SearchControls
            draft="Agen agriculture"
            onDraftChange={() => {}}
            corpus="tous"
            corpora={[
              {
                id: "1789",
                available: true,
                label: "1789",
                published: false,
                preview: true,
              },
            ]}
          />
        ),
      },
    ],
    { initialEntries: ["/recherche?q=Agen+agriculture&cursor=old"] },
  );
  render(<RouterProvider router={router} />);
  await user.selectOptions(
    screen.getByRole("combobox", { name: "Corpus" }),
    "1789",
  );
  const params = new URLSearchParams(router.state.location.search);
  expect(params.get("q")).toBe("Agen agriculture");
  expect(params.get("corpus")).toBe("1789");
  expect(params.has("cursor")).toBe(false);
  expect(
    searchUrl({ q: "Agen agriculture", corpus: "1789", cursor: "next" }),
  ).toContain("corpus=1789");
});
it("garde un corpus non disponible désactivé", () => {
  render(
    <RouterProvider
      router={createMemoryRouter([
        {
          path: "*",
          element: (
            <SearchControls
              draft=""
              onDraftChange={() => {}}
              corpora={[
                {
                  id: "1789",
                  available: false,
                  label: "1789",
                  published: false,
                  preview: false,
                },
              ]}
            />
          ),
        },
      ])}
    />,
  );
  expect(
    screen.getByRole("option", { name: "Cahiers de doléances — 1789" }),
  ).toBeDisabled();
});
