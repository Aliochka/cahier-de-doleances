import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { expect, it } from "vitest";
import { contribution } from "../features/contributions/fixtures.test-support";
import { ContributionContent } from "./contribution";

it("présente le numéro exact et les intitulés complets dans les métadonnées", () => {
  const form = {
    ...contribution.form,
    id: "4",
    name: "Grand Débat - Organisation de l'État & services publics",
  };
  render(
    <MemoryRouter>
      <ContributionContent
        detail={{
          ...contribution,
          form,
          answers: [],
          contribution: {
            ...contribution.contribution,
            submitted_at: "2019-03-18T23:30:00-11:00",
          },
        }}
      />
    </MemoryRouter>,
  );
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
    `Contribution n° ${contribution.contribution.id}`,
  );
  const metadata = screen.getByLabelText("Métadonnées de la contribution");
  expect(within(metadata).getByText("Grand Débat national")).toBeVisible();
  expect(
    within(metadata).getByRole("link", { name: form.name }),
  ).toHaveAttribute("href", "/forms/4");
  expect(
    within(metadata).getByRole("link", { name: contribution.author?.name }),
  ).toHaveAttribute("href", `/authors/${contribution.author?.id}`);
  expect(within(metadata).getByText("18 mars 2019")).toHaveAttribute(
    "datetime",
    "2019-03-18T23:30:00-11:00",
  );
  expect(screen.queryByRole("navigation")).toBeNull();
});

it("ne suppose ni consultation, ni date, ni navigation sur une contribution directe", () => {
  render(
    <MemoryRouter>
      <ContributionContent
        detail={{ ...contribution, author: null, answers: [] }}
      />
    </MemoryRouter>,
  );
  expect(screen.queryByText("Consultation", { selector: "dt" })).toBeNull();
  expect(screen.queryByText("Date", { selector: "dt" })).toBeNull();
  expect(screen.getByText("Auteur non renseigné")).toBeVisible();
  expect(screen.queryByRole("navigation")).toBeNull();
});

it.each([
  { previous: null, next: "/forms/4/contributions?contrib=2" },
  {
    previous: "/forms/4/contributions?contrib=1",
    next: "/forms/4/contributions?contrib=3",
  },
  { previous: "/forms/4/contributions?contrib=2", next: null },
  { previous: null, next: null },
])(
  "duplique exactement les destinations disponibles en haut et en bas (%#)",
  (navigation) => {
    render(
      <MemoryRouter>
        <ContributionContent
          detail={{ ...contribution, answers: [] }}
          navigation={navigation}
        />
      </MemoryRouter>,
    );
    const navigations = screen.queryAllByRole("navigation");
    if (!navigation.previous && !navigation.next) {
      expect(navigations).toHaveLength(0);
      return;
    }
    expect(navigations).toHaveLength(2);
    expect(navigations[0]).toHaveAttribute(
      "aria-label",
      "Contributions du questionnaire",
    );
    expect(navigations[1]).toHaveAttribute(
      "aria-label",
      "Contributions du questionnaire en bas de page",
    );
    for (const nav of navigations) {
      for (const [name, href] of [
        ["← Contribution précédente", navigation.previous],
        ["Contribution suivante →", navigation.next],
      ] as const) {
        const link = within(nav).queryByRole("link", { name });
        if (href) expect(link).toHaveAttribute("href", href);
        else expect(link).toBeNull();
      }
    }
  },
);

it("utilise les voisins de l’API pour un accès direct et garde les destinations par rang prioritaires", () => {
  const detail = {
    ...contribution,
    answers: [],
    previous_id: "9007199254742992",
    next_id: "9007199254742994",
  };
  const rendered = render(
    <MemoryRouter>
      <ContributionContent detail={detail} />
    </MemoryRouter>,
  );
  for (const nav of screen.getAllByRole("navigation")) {
    expect(
      within(nav).getByRole("link", { name: "← Contribution précédente" }),
    ).toHaveAttribute(
      "href",
      `/forms/${detail.form.id}/contributions/${detail.previous_id}`,
    );
    expect(
      within(nav).getByRole("link", { name: "Contribution suivante →" }),
    ).toHaveAttribute(
      "href",
      `/forms/${detail.form.id}/contributions/${detail.next_id}`,
    );
  }
  rendered.rerender(
    <MemoryRouter>
      <ContributionContent
        detail={detail}
        navigation={{
          previous: null,
          next: `/forms/${detail.form.id}/contributions?contrib=2`,
        }}
      />
    </MemoryRouter>,
  );
  expect(
    screen.queryByRole("link", { name: "← Contribution précédente" }),
  ).toBeNull();
  for (const link of screen.getAllByRole("link", {
    name: "Contribution suivante →",
  })) {
    expect(link).toHaveAttribute(
      "href",
      `/forms/${detail.form.id}/contributions?contrib=2`,
    );
  }
});
