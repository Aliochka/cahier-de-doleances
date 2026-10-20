import { expect, it } from "vitest";
import { authorPage } from "../contributions/fixtures.test-support";
import { answers } from "../questions/fixtures.test-support";
import { page as searchPage } from "../search/fixtures.test-support";
import { mergeAnswers, mergeAuthors, mergeSearch } from "./merge-pages";

it("ajoute les réponses dans l'ordre sans perdre les liens ni dupliquer les identifiants", () => {
  const first = answers.items[0];
  if (!first) throw new Error("Missing fixture");
  const next = {
    ...answers,
    items: [first, { ...first, id: "9007199254742999", text: "Autre réponse" }],
    has_next: false,
    next_cursor: null,
  };
  const merged = mergeAnswers([answers, next]);
  expect(merged.items.map((item) => item.id)).toEqual([
    first.id,
    "9007199254742999",
  ]);
  expect(merged.items[0]?.contribution_id).toBe(first.contribution_id);
  expect(merged.has_next).toBe(false);
});
it("la recherche conserve le classement de la sélection et les avertissements", () => {
  const first = searchPage.items[0];
  if (!first) throw new Error("Missing fixture");
  const next = {
    ...searchPage,
    items: [first, { ...first, answer_id: "999", rank: 21 }],
    has_next: false,
    next_cursor: null,
  };
  const merged = mergeSearch([searchPage, next]);
  expect(merged.items.map((item) => item.answer_id)).toEqual([
    ...searchPage.items.map((item) => item.answer_id),
    "999",
  ]);
  expect(merged.window).toEqual(searchPage.window);
  expect(merged.first_cursor).toBe(searchPage.first_cursor);
});
it("regroupe les contributions d'un même formulaire sur plusieurs lots", () => {
  const form = authorPage.forms[0];
  if (!form) throw new Error("Missing fixture");
  const item = form.contributions[0];
  if (!item) throw new Error("Missing fixture");
  const next = {
    ...authorPage,
    forms: [{ ...form, contributions: [item, { ...item, id: "999" }] }],
    has_next: false,
    next_after_id: null,
  };
  const merged = mergeAuthors([authorPage, next]);
  expect(merged.forms.map((item) => item.id)).toEqual(
    authorPage.forms.map((item) => item.id),
  );
  expect(merged.forms[0]?.contributions.map((item) => item.id)).toEqual([
    ...form.contributions.map((item) => item.id),
    "999",
  ]);
});
