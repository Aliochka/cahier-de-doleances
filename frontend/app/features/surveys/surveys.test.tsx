import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { expect, it } from "vitest";
import { SurveyCard } from "./survey-card";

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
