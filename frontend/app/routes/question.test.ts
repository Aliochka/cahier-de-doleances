import { RouterContextProvider } from "react-router";
import { beforeEach, expect, it, vi } from "vitest";
import {
  answers,
  question,
  stats,
} from "../features/questions/fixtures.test-support";
import { page as searchPage } from "../features/search/fixtures.test-support";
import {
  getQuestion,
  getQuestionAnswers,
  getQuestionStats,
  search,
} from "../lib/api.server";
import { loader } from "./question";

vi.mock("../lib/api.server", () => ({
  getQuestion: vi.fn(),
  getQuestionAnswers: vi.fn(),
  getQuestionStats: vi.fn(),
  search: vi.fn(),
}));
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(getQuestion).mockResolvedValue({ ok: true, data: question });
  vi.mocked(getQuestionAnswers).mockResolvedValue({ ok: true, data: answers });
  vi.mocked(getQuestionStats).mockResolvedValue({ ok: true, data: stats });
});
const args = (key = `${question.id}-${question.slug}`, search = "") => ({
  request: new Request(`http://localhost/questions/${key}${search}`),
  params: { questionKey: key },
  context: new RouterContextProvider(),
  url: new URL(`http://localhost/questions/${key}${search}`),
  pattern: "/questions/:questionKey",
});
it("conserve BIGINT, curseur opaque et annulation, sans statistiques superflues", async () => {
  const input = args(undefined, "?cursor=opaque%2B%2F%3D");
  const result = await loader(input);
  expect(getQuestion).toHaveBeenCalledWith(question.id, {
    signal: input.request.signal,
  });
  expect(getQuestionAnswers).toHaveBeenCalledWith(
    question.id,
    { cursor: "opaque+/=" },
    { signal: input.request.signal },
  );
  expect(result.data.answers).toEqual(answers);
  expect(getQuestionStats).not.toHaveBeenCalled();
  expect(result.init?.headers).toMatchObject({
    "X-Robots-Tag": "noindex, follow",
  });
});
it.each([`${question.id}-ancien-slug`, question.id])(
  "redirige %s une seule fois avec le curseur intact",
  async (key) => {
    try {
      await loader(args(key, "?cursor=opaque%2B%2F%3D"));
      throw new Error("Missing redirect");
    } catch (error) {
      expect(error).toBeInstanceOf(Response);
      if (error instanceof Response) {
        expect(error.status).toBe(308);
        expect(error.headers.get("location")).toBe(
          `${question.url}?cursor=opaque%2B%2F%3D`,
        );
      }
    }
    expect(getQuestionAnswers).not.toHaveBeenCalled();
  },
);
it("charge les choix et leurs seuls textes Autre", async () => {
  vi.mocked(getQuestion).mockResolvedValue({
    ok: true,
    data: { ...question, type: "multi_choice", display_mode: "choice" },
  });
  const result = await loader(args());
  expect(result.data.stats).toEqual(stats);
  expect(getQuestionAnswers).toHaveBeenCalledWith(
    question.id,
    { other_only: true },
    { signal: expect.any(AbortSignal) },
  );
});
it.each([
  ["missing", 404],
  ["unavailable", 503],
  ["timeout", 504],
  ["application", 500],
] as const)("préserve le statut du détail %s", async (kind, status) => {
  vi.mocked(getQuestion).mockResolvedValue({ ok: false, kind, status });
  await expect(loader(args())).rejects.toMatchObject({ init: { status } });
});
it("conserve le détail et signale une erreur partielle avec son statut HTTP", async () => {
  vi.mocked(getQuestionAnswers).mockResolvedValue({
    ok: false,
    kind: "unavailable",
    status: 503,
  });
  const result = await loader(args());
  expect(result.data.question).toEqual(question);
  expect(result.data.answers).toBeNull();
  expect(result.data.failure?.kind).toBe("unavailable");
  expect(result.init).toMatchObject({
    status: 503,
    headers: { "X-Robots-Tag": "noindex, nofollow" },
  });
});
it.each(["?cursor=", "?cursor=a&cursor=b", `?cursor=${"a".repeat(1025)}`])(
  "rejette un curseur invalide avant sa lecture",
  async (search) => {
    await expect(loader(args(undefined, search))).rejects.toMatchObject({
      init: { status: 422 },
    });
    expect(getQuestionAnswers).not.toHaveBeenCalled();
  },
);

it("canonicalise l’URL applicative normalisée sans rediriger les requêtes internes .data", async () => {
  const input = args();
  input.request = new Request(
    `http://localhost${question.url}.data?_routes=routes/question`,
  );
  const result = await loader(input);
  expect(result.data.question.id).toBe(question.id);
  expect(getQuestionAnswers).toHaveBeenCalledTimes(1);
});

it("préserve le contexte lors d’une panne des statistiques sans lire les réponses", async () => {
  vi.mocked(getQuestion).mockResolvedValue({
    ok: true,
    data: { ...question, type: "single_choice", display_mode: "choice" },
  });
  vi.mocked(getQuestionStats).mockResolvedValue({
    ok: false,
    kind: "application",
    status: 500,
  });
  const result = await loader(args());
  expect(result.data.question.form).toEqual(question.form);
  expect(result.data.stats).toBeNull();
  expect(result.init?.status).toBe(500);
  expect(getQuestionAnswers).not.toHaveBeenCalled();
});

it("sans Autre, les choix ne déclenchent pas de lecture des réponses individuelles", async () => {
  vi.mocked(getQuestion).mockResolvedValue({
    ok: true,
    data: { ...question, type: "single_choice", display_mode: "choice" },
  });
  vi.mocked(getQuestionStats).mockResolvedValue({
    ok: true,
    data: { ...stats, other_text_answers_count: 0 },
  });
  await loader(args());
  expect(getQuestionAnswers).not.toHaveBeenCalled();
});

it("ouvre la recherche sans charger les réponses ni appeler le moteur", async () => {
  const result = await loader(args(undefined, "?tab=search"));
  expect(result.data.tab).toBe("search");
  expect(result.data.search?.result).toBeNull();
  expect(getQuestionAnswers).not.toHaveBeenCalled();
  expect(search).not.toHaveBeenCalled();
});

it("recherche dans la question et garde les liens de pagination sur sa page", async () => {
  const page = {
    ...searchPage,
    items: searchPage.items.map((item) => ({
      ...item,
      question: { id: question.id, prompt: question.prompt, url: question.url },
    })),
  };
  vi.mocked(search).mockResolvedValue({ ok: true, data: page });
  const input = args(undefined, `?tab=search&q=${encodeURIComponent(page.q)}`);
  await expect(loader(input)).rejects.toMatchObject({ status: 303 });
  expect(search).toHaveBeenCalledWith(
    {
      q: page.q,
      question_id: question.id,
      page_size: 20,
    },
    { signal: input.request.signal },
  );
  const stable = await loader(
    args(
      undefined,
      `?${new URLSearchParams({
        tab: "search",
        q: page.q,
        cursor: page.first_cursor ?? "",
      })}`,
    ),
  );
  expect(stable.data.search?.result).toEqual(page);
  expect(stable.data.search?.state.path).toBe(question.url);
  expect(getQuestionAnswers).not.toHaveBeenCalled();
});

it("refuse les résultats d’une autre question", async () => {
  vi.mocked(search).mockResolvedValue({
    ok: true,
    data: {
      ...searchPage,
      items: searchPage.items.map((item) => ({
        ...item,
        question: { ...item.question, id: "1" },
      })),
    },
  });
  const result = await loader(
    args(undefined, `?tab=search&q=${encodeURIComponent(searchPage.q)}`),
  );
  expect(result.data.search?.failure?.kind).toBe("invalid_response");
  expect(result.init?.status).toBe(502);
});

it.each([
  "?tab=search&q=a&q=b",
  "?tab=search&q=x&cursor=",
  "?tab=search&q=x&page_size=21",
])("valide les paramètres de recherche %s", async (query) => {
  const result = await loader(args(undefined, query));
  expect(result.init?.status).toBe(422);
  expect(search).not.toHaveBeenCalled();
});

it("sans texte Autre, explique l’absence de recherche sans appeler le moteur", async () => {
  vi.mocked(getQuestion).mockResolvedValue({
    ok: true,
    data: {
      ...question,
      type: "single_choice",
      display_mode: "choice",
    },
  });
  vi.mocked(getQuestionStats).mockResolvedValue({
    ok: true,
    data: {
      ...stats,
      other_text_answers_count: 0,
    },
  });
  const result = await loader(args(undefined, "?tab=search&q=non"));
  expect(result.data.noSearchableText).toBe(true);
  expect(search).not.toHaveBeenCalled();
  expect(getQuestionAnswers).not.toHaveBeenCalled();
});
