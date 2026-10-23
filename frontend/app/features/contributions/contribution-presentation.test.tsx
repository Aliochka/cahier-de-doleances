import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { expect, it } from "vitest";
import { Answers } from "../questions/answers";
import { answers } from "../questions/fixtures.test-support";
import { page } from "../search/fixtures.test-support";
import { SearchResults } from "../search/search-results";
import { ContributionAnswers } from "./contribution-answers";
import { contribution } from "./fixtures.test-support";

const texts = [
  "Non",
  "  Ma parole, à moi !\n\nDeuxième paragraphe.\nUne ligne.  ",
  "École & égalité <script>reste du texte</script>\u00a0: « oui ».",
  `https://exemple.fr/${"chemin".repeat(100)}\n\n${"Une parole longue. ".repeat(1000)}`,
];

it.each(texts)(
  "préserve chaque caractère dans les trois présentations (%#)",
  (text) => {
    const answer = contribution.answers[0];
    const listed = answers.items[0];
    const result = page.items[0];
    if (!answer || !listed || !result) throw new Error("Missing fixtures");
    const views = [
      <ContributionAnswers key="full" answers={[{ ...answer, text }]} />,
      <Answers
        key="list"
        formId={contribution.form.id}
        page={{ ...answers, items: [{ ...listed, text }] }}
        path="/questions/1-test"
        cursor={null}
      />,
      <SearchResults
        key="search"
        results={{
          ...page,
          items: [
            {
              ...result,
              texts: [{ unit_type: "open_answer", unit_index: 0, text }],
            },
          ],
        }}
        state={{ q: page.q, cursor: null, page_size: 20 }}
      />,
    ];
    for (const view of views) {
      const rendered = render(<MemoryRouter>{view}</MemoryRouter>);
      expect(
        [...rendered.container.querySelectorAll("p")].filter(
          (p) => p.textContent === text,
        ),
      ).toHaveLength(1);
      expect(rendered.container.querySelector("script")).toBeNull();
      rendered.unmount();
    }
  },
);
