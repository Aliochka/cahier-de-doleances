import { render, screen } from "@testing-library/react";
import { MemoryRouter, RouterContextProvider } from "react-router";
import { beforeEach, expect, it, vi } from "vitest";
import { SurveyList } from "../features/surveys/survey-card";
import { getForm, listForms } from "../lib/api.server";
import { loader as formLoader } from "./form";
import { loader as surveysLoader } from "./surveys";

vi.mock("../lib/api.server", () => ({ listForms: vi.fn(), getForm: vi.fn() }));
beforeEach(() => vi.resetAllMocks());
const forms = [
  {
    id: "9007199254740995",
    name: "Zéro tri alphabétique",
    questions_count: 0,
    url: "/forms/9007199254740995",
  },
  {
    id: "9007199254740993",
    name: "Autre enquête",
    questions_count: 2,
    url: "/forms/9007199254740993",
  },
] satisfies [
  import("../lib/api").Forms[number],
  import("../lib/api").Forms[number],
];
const args = (path: string) => ({
  request: new Request(`http://localhost${path}`),
  params: { formId: "9007199254740993" },
  context: new RouterContextProvider(),
  url: new URL(`http://localhost${path}`),
  pattern: "/forms/:formId",
});

it("charge les formulaires sans les réordonner et propage l'annulation", async () => {
  vi.mocked(listForms).mockResolvedValue({ ok: true, data: forms });
  const input = args("/enquetes");
  const result = await surveysLoader(input);
  expect(listForms).toHaveBeenCalledWith({ signal: input.request.signal });
  expect(result.data).toEqual(forms);
  render(
    <MemoryRouter>
      <SurveyList forms={result.data} />
    </MemoryRouter>,
  );
  expect(
    screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent),
  ).toEqual(forms.map((f) => f.name));
});

it("affiche une liste vide comme un état normal", async () => {
  vi.mocked(listForms).mockResolvedValue({ ok: true, data: [] });
  const result = await surveysLoader(args("/enquetes"));
  render(
    <MemoryRouter>
      <SurveyList forms={result.data} />
    </MemoryRouter>,
  );
  expect(
    screen.getByText("Aucun formulaire disponible pour le moment."),
  ).toBeVisible();
});

it.each([
  ["application", 500],
  ["unavailable", 503],
  ["network", 503],
  ["timeout", 504],
  ["missing", 404],
] as const)("préserve l'erreur %s et son statut %i", async (kind, status) => {
  vi.mocked(listForms).mockResolvedValue({ ok: false, kind, status });
  vi.mocked(getForm).mockResolvedValue({ ok: false, kind, status });
  await expect(surveysLoader(args("/enquetes"))).rejects.toMatchObject({
    init: { status, headers: { "X-Robots-Tag": "noindex, nofollow" } },
  });
  await expect(
    formLoader(args("/forms/9007199254740993")),
  ).rejects.toMatchObject({ init: { status } });
});

it("transmet l'identifiant exact et le signal au loader formulaire", async () => {
  const form = { ...forms[1], questions: [] };
  vi.mocked(getForm).mockResolvedValue({ ok: true, data: form });
  const input = args("/forms/9007199254740993");
  expect((await formLoader(input)).data).toEqual({ mode: "form", form });
  expect(getForm).toHaveBeenCalledWith("9007199254740993", {
    signal: input.request.signal,
  });
});

it.each(["?contrib=2", "?contrib=", "?contrib=invalide"])(
  "traite explicitement l'ancienne URL %s sans lire ni substituer le formulaire",
  async (query) => {
    const result = await formLoader(args(`/forms/9007199254740993${query}`));
    expect(result.data).toEqual({
      mode: "contribution",
      formId: "9007199254740993",
    });
    expect(result.init).toMatchObject({
      status: 501,
      headers: {
        "Cache-Control": "private, no-store",
        "X-Robots-Tag": "noindex, nofollow",
      },
    });
    expect(getForm).not.toHaveBeenCalled();
  },
);
