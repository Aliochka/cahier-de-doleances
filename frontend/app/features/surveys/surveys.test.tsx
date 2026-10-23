import { render, screen, within } from "@testing-library/react";
import { renderToString } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { expect, it } from "vitest";
import type { Consultation } from "./catalogue";
import { SurveyCard } from "./survey-card";
import { SurveyCatalogue } from "./survey-catalogue";

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

it("classe les questionnaires connus et garde les autres sans rattachement supposé", () => {
  const forms = [
    {
      id: "4",
      name: "Grand Débat - Organisation de l'État & services publics",
      questions_count: 33,
      url: "/forms/4",
    },
    {
      id: "2",
      name: "Grand Débat - Organisation de l'État & services publics (questions rapides)",
      questions_count: 12,
      url: "/forms/2",
    },
    {
      id: "9007199254740995",
      name: "Grand Débat - Intitulé inconnu (questions rapides)",
      questions_count: 0,
      url: "/forms/9007199254740995",
    },
  ];
  const before = structuredClone(forms);
  render(
    <MemoryRouter>
      <SurveyCatalogue forms={forms} />
    </MemoryRouter>,
  );
  const known = screen.getByRole("region", { name: "Grand Débat national" });
  expect(within(known).getByText("2019")).toBeVisible();
  expect(within(known).getByText("Questionnaire rapide")).toBeVisible();
  expect(within(known).getByText("Questionnaire détaillé")).toBeVisible();
  expect(within(known).getByText("12 questions")).toBeVisible();
  expect(
    within(known)
      .getAllByRole("link")
      .map((link) => link.getAttribute("href")),
  ).toEqual(["/forms/4", "/forms/2"]);
  expect(
    within(known)
      .getAllByRole("heading", { level: 3 })
      .map((heading) => heading.textContent),
  ).toEqual([
    "Organisation de l'État & services publics",
    "Organisation de l'État & services publics",
  ]);
  const unknown = screen.getByRole("region", {
    name: "Consultation non renseignée",
  });
  expect(
    within(unknown).getByRole("link", { name: forms[2]?.name }),
  ).toHaveAttribute("href", "/forms/9007199254740995");
  expect(within(unknown).queryByText("Questionnaire rapide")).toBeNull();
  expect(within(unknown).getByText("0 questions")).toBeVisible();
  expect(forms).toEqual(before);
});

it("affiche plusieurs fonds ouverts, sans inventer les métadonnées manquantes", () => {
  const catalogue: Consultation[] = [
    {
      id: "first",
      name: "Première consultation",
      period: "2020–2021",
      description: "Présentation du premier fonds.",
      questionnaires: {
        "9007199254740993": {
          title: "Premier questionnaire",
          type: "Questionnaire détaillé",
        },
      },
    },
    {
      id: "second",
      name: "Deuxième consultation",
      questionnaires: {
        "9007199254740995": { title: "Deuxième questionnaire" },
      },
    },
  ];
  const forms = [
    {
      id: "9007199254740995",
      name: "Titre source 2",
      questions_count: 2,
      url: "/forms/9007199254740995",
    },
    {
      id: "9007199254740993",
      name: "Titre source 1",
      questions_count: 1,
      url: "/forms/9007199254740993",
    },
  ];
  const { container } = render(
    <MemoryRouter>
      <SurveyCatalogue forms={forms} catalogue={catalogue} />
    </MemoryRouter>,
  );
  expect(
    screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent),
  ).toEqual(["Première consultation", "Deuxième consultation"]);
  expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(2);
  expect(screen.getByText("Présentation du premier fonds.")).toBeVisible();
  expect(screen.getByText("2020–2021")).toBeVisible();
  expect(container.querySelector("details, [aria-expanded]")).toBeNull();
  const html = renderToString(
    <MemoryRouter>
      <SurveyCatalogue forms={forms} catalogue={catalogue} />
    </MemoryRouter>,
  );
  expect(html).toContain("Premier questionnaire");
  expect(html).toContain("Deuxième questionnaire");
});
