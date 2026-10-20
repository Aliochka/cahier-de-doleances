import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { expect, it } from "vitest";
import {
  ContributionAnswers,
  duplicatesStructuredContent,
} from "./contribution-answers";
import { contribution } from "./fixtures.test-support";

const choice = contribution.answers[2];
const numeric = contribution.answers[3];
const open = contribution.answers[0];
if (!choice || !numeric || !open)
  throw new Error("Missing contribution fixtures");
it.each([
  {
    ...choice,
    question: { ...choice.question, type: "single_choice" },
    selected_options: [{ id: "1", label: "Oui", position: 1 }],
    other_text: [],
    text: "Oui",
  },
  { ...choice, text: "Choix B\nChoix A\nAutre réponse" },
  { ...choice, text: "Autre réponse" },
  { ...choice, text: "Choix B\nChoix A" },
  { ...choice, selected_options: [], text: "Autre réponse" },
  { ...numeric, text: "42" },
])(
  "les champs structurés et leur copie textuelle sont affichés une seule fois",
  (answer) => {
    expect(duplicatesStructuredContent(answer)).toBe(true);
    const { container } = render(
      <MemoryRouter>
        <ContributionAnswers answers={[answer]} />
      </MemoryRouter>,
    );
    expect(container.querySelectorAll("section > p")).toHaveLength(
      answer.other_text.length ? 1 : answer.value !== null ? 1 : 0,
    );
    expect(screen.getByRole("heading").querySelector("a")).toHaveAttribute(
      "href",
      `/questions/${answer.question.id}-${answer.question.slug}`,
    );
  },
);
it.each([
  { ...choice, text: "Choix B\nUne précision citoyenne distincte" },
  { ...choice, text: "Un commentaire supplémentaire" },
  { ...open, text: "Oui" },
  { ...choice, text: "autre réponse" },
])("les textes distincts et les réponses ouvertes sont conservés", (answer) => {
  expect(duplicatesStructuredContent(answer)).toBe(false);
  render(
    <MemoryRouter>
      <ContributionAnswers answers={[answer]} />
    </MemoryRouter>,
  );
  expect(screen.getByRole("region").textContent).toContain(answer.text);
});
it("des réponses différentes ne sont jamais fusionnées", () => {
  const { container } = render(
    <MemoryRouter>
      <ContributionAnswers
        answers={[
          { ...choice, text: "Autre réponse" },
          { ...choice, id: "999", text: "Autre réponse" },
        ]}
      />
    </MemoryRouter>,
  );
  expect(container.querySelectorAll("section")).toHaveLength(2);
  expect(screen.getAllByText("Autre : Autre réponse")).toHaveLength(2);
});
