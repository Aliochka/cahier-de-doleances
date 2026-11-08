import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { HistoricalText } from "./historical-text";

it("compose les paragraphes XML, garde les titres et normalise uniquement les espaces", () => {
  render(
    <HistoricalText
      paragraphs={[
        {
          kind: "heading",
          start_offset: 0,
          end_offset: 10,
          fragments: [{ text: "  Justice\n ", selected: false, anchor: null }],
        },
        {
          kind: "paragraph",
          start_offset: 10,
          end_offset: 60,
          fragments: [
            { text: "  Avant\n    ", selected: false, anchor: null },
            {
              text: "😀 séné-\n chaussée\t  é",
              selected: true,
              anchor: "passage-stable",
            },
            { text: "\u00a0  après.\n", selected: false, anchor: null },
          ],
        },
        {
          kind: "paragraph",
          start_offset: 60,
          end_offset: 90,
          fragments: [
            { text: "Une suite\n     longue.", selected: true, anchor: null },
            { text: " Fin.", selected: false, anchor: null },
          ],
        },
      ]}
    />,
  );
  const region = screen.getByRole("region", {
    name: "Texte intégral du cahier",
  });
  expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent(
    "Justice",
  );
  expect(region.querySelectorAll("p")).toHaveLength(2);
  expect(region.querySelectorAll("mark")).toHaveLength(2);
  expect(region.querySelectorAll("[id]")).toHaveLength(1);
  expect(document.getElementById("passage-stable")).toHaveTextContent(
    "😀 séné- chaussée é",
  );
  for (const fragment of region.querySelectorAll("span, mark"))
    expect(fragment.textContent).not.toMatch(/[\n\t\u00a0]| {2}/u);
  expect(region.textContent).not.toContain("sénéchaussée");
  expect(
    region.querySelector("p")?.textContent?.replace(/\s+/gu, " "),
  ).toContain("Avant 😀");
});
