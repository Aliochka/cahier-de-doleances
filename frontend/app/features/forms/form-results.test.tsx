import { render, screen, within } from "@testing-library/react";
import { renderToString } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { expect, it } from "vitest";
import type { FormDetail, QuestionStatistics } from "../../lib/api";
import { FormQuestions } from "./form-questions";
import { isCompleteYesNo, palette, ResultChart } from "./result-charts";

type Category = QuestionStatistics["categories"][number];
type Question = FormDetail["questions"][number];
const binary: QuestionStatistics & { categories: [Category, Category] } = {
  question_id: "9007199254741022",
  type: "single_choice",
  total_answers: 10,
  answered_contributions_count: 8,
  total_option_selections: 10,
  total_selections: 10,
  other_text_answers_count: 0,
  percentage_denominator: "total_answers",
  percentage_decimal_places: 2,
  categories: [
    {
      option_id: "9007199254742001",
      kind: "option",
      label: "Oui",
      position: 1,
      count: 7,
      percentage: 70,
    },
    {
      option_id: "9007199254742002",
      kind: "option",
      label: "Non",
      position: 2,
      count: 3,
      percentage: 30,
    },
  ],
};
const form: FormDetail & { questions: [Question, Question] } = {
  id: "9007199254740995",
  name: "Questionnaire synthétique",
  url: "/forms/9007199254740995",
  questions_count: 2,
  statistics_availability: {
    status: "available",
    generation_id: "generation-test",
    method_version: "historical-answers-v1",
    calculated_at: "2026-10-20T17:49:01+02:00",
  },
  questions: [
    {
      id: binary.question_id,
      form_id: "9007199254740995",
      type: "single_choice",
      position: 1,
      prompt: "Un intitulé très long ".repeat(15),
      slug: "choix",
      url: `/questions/${binary.question_id}-choix`,
      answers_count: 10,
      statistics: binary,
    },
    {
      id: "9007199254741023",
      form_id: "9007199254740995",
      type: "text",
      position: 2,
      prompt: "Pourquoi ?",
      slug: "pourquoi",
      url: "/questions/9007199254741023-pourquoi",
      answers_count: 0,
      statistics: null,
    },
  ],
};
function view(value: FormDetail = form) {
  return render(
    <MemoryRouter>
      <FormQuestions form={value} />
    </MemoryRouter>,
  );
}
it("SSR : questions ordonnées, ancres, valeurs, détails et BIGINT sans Recharts", () => {
  const html = renderToString(
    <MemoryRouter>
      <FormQuestions form={form} />
    </MemoryRouter>,
  );
  const document = new DOMParser().parseFromString(html, "text/html");
  expect(document.querySelectorAll('section[id^="question-"]')).toHaveLength(2);
  expect(document.querySelectorAll("details table")).toHaveLength(1);
  expect(document.querySelector("details[open]")).toBeNull();
  expect(document.querySelector('[data-chart-kind="yes-no"]')).not.toBeNull();
  expect(
    document.querySelector("[data-chart-kind]")?.closest("details"),
  ).toBeNull();
  expect(document.querySelector("nav")).toBeNull();
  expect(document.querySelector("h2 a")?.getAttribute("href")).toBe(
    form.questions[0].url,
  );
  expect(document.body.textContent).toContain("7 · 70 %");
  expect(document.body.textContent).toContain(
    "Contributions distinctes ayant répondu",
  );
  expect(html).not.toMatch(
    /recharts|<svg|Afficher le graphique|Retour au sommaire|Consulter la page/,
  );
  expect(document.querySelectorAll("h2")[0]?.textContent).toBe(
    form.questions[0].prompt,
  );
  expect(
    new Set([...document.querySelectorAll("[id]")].map((x) => x.id)).size,
  ).toBe(document.querySelectorAll("[id]").length);
});
it.each([
  { ...binary, type: "multi_choice" as const },
  { ...binary, total_answers: 11 },
  { ...binary, other_text_answers_count: 1 },
  {
    ...binary,
    categories: [
      ...binary.categories,
      {
        option_id: null,
        kind: "other_text" as const,
        label: "Autre",
        position: null,
        count: 1,
        percentage: 10,
      },
    ],
  },
  {
    ...binary,
    categories: [
      binary.categories[0],
      { ...binary.categories[1], label: "Je ne sais pas" },
    ],
  },
])("un Oui/Non non exclusif ou incomplet n'est pas empilé", (value) => {
  expect(isCompleteYesNo(value)).toBe(false);
});
it("choix multiples : valeurs supérieures à 100 % cumulés et Autre distinct", () => {
  const stats: QuestionStatistics = {
    ...binary,
    type: "multi_choice",
    total_option_selections: 15,
    total_selections: 17,
    other_text_answers_count: 2,
    categories: [
      { ...binary.categories[0], count: 9, percentage: 90 },
      { ...binary.categories[1], count: 6, percentage: 60 },
      {
        option_id: null,
        kind: "other_text",
        label: "Autre (texte libre)",
        position: null,
        count: 2,
        percentage: 20,
      },
    ],
  };
  const { container } = render(<ResultChart stats={stats} />);
  expect(container.querySelector('[data-chart-kind="bars"]')).toBeTruthy();
  expect(screen.getByText("Plusieurs réponses possibles")).toBeVisible();
  expect(screen.getByText("9 · 90 %")).toBeVisible();
  expect(screen.getByText("6 · 60 %")).toBeVisible();
  expect(screen.getByText(/peut accompagner une option/)).toBeVisible();
});
it("questions ouvertes : zéro réel, pas un nombre de témoignages consultables", () => {
  view();
  expect(screen.getByText("0 réponses enregistrées")).toBeVisible();
  expect(
    screen.getByRole("link", {
      name: "Pourquoi ?",
    }),
  ).toHaveAttribute("href", form.questions[1].url);
  const summaries = screen.getAllByText("Voir les détails statistiques", {
    exact: false,
  });
  expect(summaries).toHaveLength(1);
});
it("indisponibilité : questionnaire et liens conservés, aucun faux zéro ou graphique", () => {
  const { container } = view({
    ...form,
    statistics_availability: { status: "unavailable", reason: "incompatible" },
  });
  expect(screen.getAllByText("Nombre de réponses indisponible.")).toHaveLength(
    2,
  );
  expect(screen.getByText(/Les statistiques de cette question/)).toBeVisible();
  expect(container.querySelector("[data-chart-kind]")).toBeNull();
  expect(screen.queryByText("0 réponses enregistrées")).toBeNull();
});
it("les options à zéro sont visibles et la division par zéro est évitée", () => {
  const { container } = render(
    <ResultChart
      stats={{
        ...binary,
        total_answers: 0,
        total_selections: 0,
        total_option_selections: 0,
        answered_contributions_count: 0,
        categories: binary.categories.map((c) => ({
          ...c,
          count: 0,
          percentage: 0,
        })),
      }}
    />,
  );
  expect(screen.getAllByText("0 · 0 %")).toHaveLength(2);
  expect(container.innerHTML).not.toMatch(/NaN|Infinity/);
  expect(screen.getByText(/Aucune réponse enregistrée/)).toBeVisible();
});
it("37 questions restent toutes présentes dans l'ordre, avec types futurs et positions absentes", () => {
  const value = {
    ...form,
    questions_count: 37,
    questions: Array.from({ length: 37 }, (_, i) => ({
      ...form.questions[1],
      id: String(9007199254741100n + BigInt(i)),
      prompt: `Question ${i + 1} complète`,
      position: i === 36 ? null : i + 1,
      type: i === 36 ? "constructor" : "text",
    })),
  };
  view(value);
  const list = screen.getByRole("list", { name: "Questions du formulaire" });
  expect(within(list).getAllByRole("heading")).toHaveLength(37);
  expect(within(list).getAllByRole("heading")[36]).toHaveTextContent(
    "Question 37 complète",
  );
});
it("palette : contrastes des six couleurs sur la surface claire", () => {
  const luminance = (hex: string) => {
    const [r = 0, g = 0, b = 0] = [1, 3, 5].map((i) => {
      const v = Number.parseInt(hex.slice(i, i + 2), 16) / 255;
      return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  for (const color of palette)
    expect(
      (luminance("#fbfaf6") + 0.05) / (luminance(color) + 0.05),
    ).toBeGreaterThan(4.5);
});
