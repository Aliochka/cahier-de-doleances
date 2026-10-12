import { render, screen } from "@testing-library/react";
import { MemoryRouter, RouterContextProvider } from "react-router";
import { beforeEach, expect, it, vi } from "vitest";
import { AuthorForms } from "../features/authors/author-forms";
import { ContributionAnswers } from "../features/contributions/contribution-answers";
import {
  authorPage,
  contribution,
  publicAuthor,
} from "../features/contributions/fixtures.test-support";
import { createPublicApi } from "../lib/api";
import { getAuthor, getAuthorForms, getContribution } from "../lib/api.server";
import { loader as authorLoader } from "./author";
import { loader as contributionLoader } from "./contribution";

vi.mock("../lib/api.server", () => ({
  getAuthor: vi.fn(),
  getAuthorForms: vi.fn(),
  getContribution: vi.fn(),
}));
beforeEach(() => vi.resetAllMocks());
const args = (path: string) => ({
  request: new Request(`http://localhost${path}`),
  url: new URL(`http://localhost${path}`),
  params: {
    authorId: publicAuthor.id,
    formId: contribution.form.id,
    contributionId: contribution.contribution.id,
  },
  context: new RouterContextProvider(),
  pattern: path,
});
it("charge l'auteur et un lot de contributions avec les identifiants exacts et le signal", async () => {
  vi.mocked(getAuthor).mockResolvedValue({ ok: true, data: publicAuthor });
  vi.mocked(getAuthorForms).mockResolvedValue({ ok: true, data: authorPage });
  const input = args(`/authors/${publicAuthor.id}?after_id=9007199254742993`);
  const result = await authorLoader(input);
  expect(getAuthorForms).toHaveBeenCalledWith(
    publicAuthor.id,
    { after_id: "9007199254742993" },
    { signal: input.request.signal },
  );
  expect(result.data.page).toEqual(authorPage);
  render(
    <MemoryRouter>
      <AuthorForms
        page={authorPage}
        path={`/authors/${publicAuthor.id}`}
        after={null}
      />
    </MemoryRouter>,
  );
  expect(
    screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent),
  ).toEqual(["Participation citoyenne", "Autre formulaire"]);
  const links = screen.getAllByRole("link", {
    name: /Consulter la contribution/,
  });
  expect(links).toHaveLength(3);
  expect(links[0]).toHaveAttribute(
    "href",
    `/forms/${contribution.form.id}/contributions/${contribution.contribution.id}`,
  );
  expect(
    screen.getByRole("link", { name: "Voir les contributions suivantes" }),
  ).toHaveAttribute(
    "href",
    `/authors/${publicAuthor.id}?after_id=9007199254742994`,
  );
});
it("un auteur sans contribution conserve un état vide normal", () => {
  render(
    <MemoryRouter>
      <AuthorForms
        page={{
          ...authorPage,
          forms: [],
          has_next: false,
          next_after_id: null,
        }}
        path="/authors/100"
        after={null}
      />
    </MemoryRouter>,
  );
  expect(
    screen.getByText("Aucune contribution consultable dans ce lot."),
  ).toBeVisible();
});
it.each(["", "0", "invalid", "1&after_id=2"])(
  "rejette un curseur auteur invalide %s",
  async (after) => {
    await expect(
      authorLoader(args(`/authors/${publicAuthor.id}?after_id=${after}`)),
    ).rejects.toMatchObject({ init: { status: 422 } });
    expect(getAuthor).not.toHaveBeenCalled();
  },
);
it.each([
  ["missing", 404],
  ["application", 500],
  ["unavailable", 503],
  ["server_timeout", 504],
] as const)(
  "préserve le statut %s sur les lectures essentielles",
  async (kind, status) => {
    vi.mocked(getAuthor).mockResolvedValue({ ok: false, kind, status });
    vi.mocked(getContribution).mockResolvedValue({ ok: false, kind, status });
    await expect(authorLoader(args("/authors/404"))).rejects.toMatchObject({
      init: { status },
    });
    await expect(
      contributionLoader(args("/forms/1/contributions/404")),
    ).rejects.toMatchObject({ init: { status } });
  },
);
it("garde le nom public lorsque la liste secondaire est indisponible", async () => {
  vi.mocked(getAuthor).mockResolvedValue({ ok: true, data: publicAuthor });
  vi.mocked(getAuthorForms).mockResolvedValue({
    ok: false,
    kind: "unavailable",
    status: 503,
  });
  const result = await authorLoader(args(`/authors/${publicAuthor.id}`));
  expect(result.data.author).toEqual(publicAuthor);
  expect(result.data.page).toBeNull();
  expect(result.init).toMatchObject({
    status: 503,
    headers: { "X-Robots-Tag": "noindex, nofollow" },
  });
});
it("la contribution charge uniquement son endpoint et vérifie le formulaire", async () => {
  vi.mocked(getContribution).mockResolvedValue({
    ok: true,
    data: contribution,
  });
  const input = args(
    `/forms/${contribution.form.id}/contributions/${contribution.contribution.id}`,
  );
  expect((await contributionLoader(input)).data).toEqual(contribution);
  expect(getContribution).toHaveBeenCalledWith(
    contribution.form.id,
    contribution.contribution.id,
    { signal: input.request.signal },
  );
  await expect(
    contributionLoader({ ...input, params: { ...input.params, formId: "42" } }),
  ).rejects.toMatchObject({ init: { status: 404 } });
});
it("affiche chaque réponse ordonnée avec ancre, texte complet échappé et choix", () => {
  const { container } = render(
    <MemoryRouter>
      <ContributionAnswers answers={contribution.answers} />
    </MemoryRouter>,
  );
  expect([...container.querySelectorAll("section")].map((el) => el.id)).toEqual(
    contribution.answers.map((a) => `answer-${a.id}`),
  );
  expect(
    screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent),
  ).toEqual(contribution.answers.map((a) => a.question.prompt));
  expect(container.querySelector("script")).toBeNull();
  expect(container.textContent).toContain(contribution.answers[0]?.text);
  expect(
    screen.getByRole("list", { name: "Choix sélectionnés" }).textContent,
  ).toBe("Choix BChoix A");
  expect(screen.getByText("Autre : Autre réponse")).toBeVisible();
  expect(screen.getByText("42")).toBeVisible();
});
it("ne fabrique aucune réponse absente", () => {
  render(<ContributionAnswers answers={[]} />);
  expect(
    screen.getByText(
      "Cette contribution ne contient aucune réponse consultable.",
    ),
  ).toBeVisible();
});
it("le transport conserve les chaînes, ne transmet pas les cookies et valide les nouvelles réponses", async () => {
  const transport = vi
    .fn<typeof fetch>()
    .mockResolvedValueOnce(Response.json(publicAuthor))
    .mockResolvedValueOnce(Response.json(authorPage))
    .mockResolvedValueOnce(Response.json(contribution));
  const api = createPublicApi("", transport);
  expect(await api.getAuthor(publicAuthor.id)).toEqual({
    ok: true,
    data: publicAuthor,
  });
  expect(
    await api.getAuthorForms(publicAuthor.id, { after_id: "9007199254742993" }),
  ).toEqual({ ok: true, data: authorPage });
  expect(
    await api.getContribution(
      contribution.form.id,
      contribution.contribution.id,
    ),
  ).toEqual({ ok: true, data: contribution });
  expect(transport.mock.calls[1]?.[0]).toBe(
    `/api/v1/authors/${publicAuthor.id}/forms?after_id=9007199254742993`,
  );
  for (const [, options] of transport.mock.calls)
    expect(options).toMatchObject({ credentials: "omit", cache: "no-store" });
});
it.each([
  {
    ...contribution,
    answers: [contribution.answers[0], contribution.answers[0]],
  },
  {
    ...contribution,
    contribution: { ...contribution.contribution, id: 9007199254742992 },
  },
  {
    ...contribution,
    answers: [
      {
        ...contribution.answers[0],
        question: { ...contribution.answers[0]?.question, form_id: "999" },
      },
    ],
  },
])(
  "rejette les IDs numériques, les ancres dupliquées et les incohérences de formulaire",
  async (payload) => {
    const api = createPublicApi(
      "",
      vi.fn<typeof fetch>().mockResolvedValue(Response.json(payload)),
    );
    expect(
      await api.getContribution(
        contribution.form.id,
        contribution.contribution.id,
      ),
    ).toEqual({ ok: false, kind: "invalid_response" });
  },
);
