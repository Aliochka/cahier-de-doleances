import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { expect, it } from "vitest";
import type { FormDetail } from "../../lib/api";
import { QuestionList } from "./question-list";
import { SurveyCard } from "./survey-card";

const questions = [
  {
    id: "9007199254741022",
    form_id: "9007199254740993",
    prompt: `Un intitulé très long : ${"consultation ".repeat(50)}`,
    type: "text",
    position: 1,
    slug: "long",
    url: "/questions/9007199254741022-long",
  },
  {
    id: "9007199254741020",
    form_id: "9007199254740993",
    prompt: "Choisir une possibilité",
    type: "single_choice",
    position: 2,
    slug: "unique",
    url: "/questions/9007199254741020-unique",
  },
  {
    id: "9007199254741021",
    form_id: "9007199254740993",
    prompt: "Choisir plusieurs possibilités",
    type: "multi_choice",
    position: null,
    slug: "multiple",
    url: "/questions/9007199254741021-multiple",
  },
] satisfies [
  FormDetail["questions"][number],
  FormDetail["questions"][number],
  FormDetail["questions"][number],
];

it("présente le titre, le compteur et un lien React sans perte BIGINT", () => {
  render(
    <MemoryRouter>
      <SurveyCard
        form={{
          id: "9007199254740993",
          name: "Citoyenneté",
          questions_count: 1,
          url: "/forms/9007199254740993",
        }}
      />
    </MemoryRouter>,
  );
  expect(screen.getByRole("link", { name: "Citoyenneté" })).toHaveAttribute(
    "href",
    "/forms/9007199254740993",
  );
  expect(screen.getByText("1 question")).toBeVisible();
});

it("conserve toutes les questions, leur texte complet et l'ordre API sans lien factice", () => {
  render(<QuestionList questions={questions} />);
  const items = within(
    screen.getByRole("list", { name: "Questions du formulaire" }),
  ).getAllByRole("listitem");
  expect(items).toHaveLength(3);
  expect(
    items.map((item) => within(item).getByRole("heading").textContent),
  ).toEqual(questions.map((question) => question.prompt));
  expect(items[0]).toHaveTextContent("Réponse libre");
  expect(items[1]).toHaveTextContent("Choix unique");
  expect(items[2]).toHaveTextContent("Choix multiples");
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});

it("annonce un questionnaire vide et accepte un type futur sans l'inventer", () => {
  const { rerender } = render(<QuestionList questions={[]} />);
  expect(
    screen.getByText("Ce formulaire ne contient aucune question."),
  ).toBeVisible();
  rerender(
    <QuestionList questions={[{ ...questions[0], type: "constructor" }]} />,
  );
  expect(screen.getByText("Question 1")).toBeVisible();
  expect(screen.queryByText("Réponse libre")).not.toBeInTheDocument();
});
