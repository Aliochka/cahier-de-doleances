import { render, screen, within } from "@testing-library/react";
import { renderToString } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { expect, it, vi } from "vitest";
import { Answers } from "./answers";
import { answers, stats } from "./fixtures.test-support";
import { Statistics } from "./statistics";

vi.mock("./stats-chart", () => ({
  default: ({ stats: value }: { stats: typeof stats }) => (
    <div data-testid="chart">
      {value.categories
        .map((c) => `${c.label}: ${c.count} / ${c.percentage}`)
        .join("; ")}
    </div>
  ),
}));

it("préserve textes, paragraphes et auteurs publics sans liens indisponibles ni HTML brut", () => {
  render(
    <MemoryRouter>
      <Answers
        page={answers}
        path="/questions/9007199254741022-test"
        cursor={null}
      />
    </MemoryRouter>,
  );
  expect(screen.getByText("Auteur anonyme")).toBeVisible();
  expect(
    screen.getByText(
      (_text, element) =>
        element?.tagName === "P" &&
        element.textContent === answers.items[0]?.text,
    ),
  ).toBeVisible();
  expect(document.querySelector("script")).toBeNull();
  expect(screen.getAllByRole("link")).toHaveLength(1);
  expect(
    screen.getByRole("link", { name: "Voir les réponses suivantes" }),
  ).toHaveAttribute(
    "href",
    "/questions/9007199254741022-test?cursor=opaque%2B%2F%3D",
  );
  expect(screen.getByText(/Texte abrégé/)).toBeVisible();
});
it("annonce une fin de pagination et un lot vide sans numéro de page", () => {
  render(
    <MemoryRouter>
      <Answers
        page={{ ...answers, items: [], has_next: false, next_cursor: null }}
        path="/questions/1-test"
        cursor="opaque"
      />
    </MemoryRouter>,
  );
  expect(
    screen.getByText("Aucune réponse consultable dans ce lot."),
  ).toBeVisible();
  expect(
    screen.queryByRole("link", { name: "Voir les réponses suivantes" }),
  ).toBeNull();
  expect(
    screen.getByRole("link", { name: "Retour aux premières réponses" }),
  ).toHaveAttribute("href", "/questions/1-test");
});
it("utilise les mêmes données non renormalisées dans le tableau et le graphique", async () => {
  render(<Statistics stats={stats} />);
  const table = screen.getByRole("table");
  const rows = within(table).getAllByRole("row").slice(1);
  expect(
    rows.map((row) => within(row).getByRole("rowheader").textContent),
  ).toEqual(stats.categories.map((c, i) => `${i + 1}. ${c.label}`));
  expect(rows[0]).toHaveTextContent("80 %");
  expect(rows[1]).toHaveTextContent("50 %");
  expect(
    screen.getByText(/somme des pourcentages peut donc dépasser 100/),
  ).toBeVisible();
  expect(await screen.findByTestId("chart")).toHaveTextContent(
    "Deuxième option: 5 / 50",
  );
});
it("produit le tableau complet au SSR sans charger Recharts ni accéder aux dimensions du navigateur", () => {
  const html = renderToString(<Statistics stats={stats} />);
  expect(html).toContain("<table");
  expect(html).toContain("Deuxième option");
  expect(html).toContain("50");
  expect(html).not.toContain('data-testid="chart"');
});
it("distingue zéro réponse et absence de catégories", () => {
  render(
    <Statistics
      stats={{
        ...stats,
        type: "single_choice",
        total_answers: 0,
        categories: [],
      }}
    />,
  );
  expect(
    screen.getByText("Aucune réponse enregistrée pour cette question."),
  ).toBeVisible();
  expect(
    screen.getByText("Aucune option statistique disponible."),
  ).toBeVisible();
  expect(screen.queryByText(/somme des pourcentages/)).toBeNull();
});

it("affiche la date historique sans dépendre du fuseau du navigateur", () => {
  render(
    <MemoryRouter>
      <Answers
        page={{
          ...answers,
          items: answers.items.map((answer) => ({
            ...answer,
            submitted_at: "2019-01-15T00:15:00",
          })),
        }}
        path="/questions/1-test"
        cursor={null}
      />
    </MemoryRouter>,
  );
  expect(screen.getByText("15 janvier 2019")).toHaveAttribute(
    "datetime",
    "2019-01-15T00:15:00",
  );
});
