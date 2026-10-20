import { afterEach, describe, expect, it, vi } from "vitest";
import { API_TIMEOUT_MS, createPublicApi, httpFailure } from "./api";
import { getForm } from "./api.server";
import { failureStatus, requireApiData } from "./api-errors";

const form = {
  id: "9007199254740993",
  name: "Exemple",
  url: "/forms/9007199254740993",
  questions_count: 0,
  statistics_availability: {
    status: "unavailable" as const,
    reason: "absent" as const,
  },
  questions: [],
};
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

it("conserve BIGINT, paramètres et politique publique sans cookies", async () => {
  const transport = vi
    .fn<typeof fetch>()
    .mockResolvedValue(Response.json(form));
  const result = await createPublicApi("", transport).getForm(form.id, {
    query: new URLSearchParams({ test: "école & lecture" }),
  });
  expect(result).toEqual({ ok: true, data: form });
  expect(transport).toHaveBeenCalledWith(
    "/api/v1/forms/9007199254740993?test=%C3%A9cole+%26+lecture",
    expect.objectContaining({
      credentials: "omit",
      cache: "no-store",
      method: "GET",
      redirect: "error",
    }),
  );
});
it("accepte une liste vide et rejette un identifiant invalide sans requête", async () => {
  const transport = vi.fn<typeof fetch>().mockResolvedValue(Response.json([]));
  expect(await createPublicApi("", transport).listForms()).toEqual({
    ok: true,
    data: [],
  });
  expect(await createPublicApi("", transport).getForm("../secret")).toEqual({
    ok: false,
    kind: "request",
  });
  expect(transport).toHaveBeenCalledTimes(1);
});

it.each([
  [400, "request"],
  [422, "request"],
  [401, "denied"],
  [403, "denied"],
  [404, "missing"],
  [500, "application"],
  [502, "unavailable"],
  [503, "unavailable"],
  [504, "server_timeout"],
  [408, "server_timeout"],
] as const)(
  "classifie HTTP %s sans exposer son corps",
  async (status, kind) => {
    const transport = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        Response.json({ detail: "private sql token" }, { status }),
      );
    const result = await createPublicApi("", transport).getForm("1");
    expect(result).toEqual({ ok: false, kind, status });
    expect(JSON.stringify(result)).not.toContain("private");
  },
);
it("distingue une erreur réseau d'une réponse JSON invalide", async () => {
  const transport = vi
    .fn<typeof fetch>()
    .mockRejectedValue(new Error("private internal host"));
  expect(await createPublicApi("", transport).listForms()).toEqual({
    ok: false,
    kind: "network",
  });
  transport.mockResolvedValue(new Response("invalid json"));
  expect(await createPublicApi("", transport).listForms()).toEqual({
    ok: false,
    kind: "invalid_response",
  });
  transport.mockResolvedValue(Response.json({ wrong: true }));
  expect(await createPublicApi("", transport).listForms()).toEqual({
    ok: false,
    kind: "invalid_response",
  });
});

function hangingFetch(): typeof fetch {
  return (_input, options) =>
    new Promise((_resolve, reject) =>
      options?.signal?.addEventListener(
        "abort",
        () => reject(new DOMException("Aborted", "AbortError")),
        { once: true },
      ),
    );
}
it("borne les requêtes et distingue timeout et annulation", async () => {
  vi.useFakeTimers();
  const client = createPublicApi("", hangingFetch());
  const pending = client.listForms({ timeoutMs: 90_000 });
  await vi.advanceTimersByTimeAsync(API_TIMEOUT_MS);
  expect(await pending).toEqual({ ok: false, kind: "timeout" });
  const controller = new AbortController();
  const cancelled = client.listForms({ signal: controller.signal });
  controller.abort();
  expect(await cancelled).toEqual({ ok: false, kind: "cancelled" });
  expect(await client.listForms({ signal: controller.signal })).toEqual({
    ok: false,
    kind: "cancelled",
  });
  expect(vi.getTimerCount()).toBe(0);
});
it("garde la limite active pendant la lecture du corps", async () => {
  vi.useFakeTimers();
  const transport = vi.fn<typeof fetch>().mockImplementation(
    async (_input, options) =>
      new Response(
        new ReadableStream({
          start(stream) {
            options?.signal?.addEventListener("abort", () =>
              stream.error(new DOMException("Aborted", "AbortError")),
            );
          },
        }),
      ),
  );
  const pending = createPublicApi("", transport).listForms();
  await vi.advanceTimersByTimeAsync(API_TIMEOUT_MS);
  expect(await pending).toEqual({ ok: false, kind: "timeout" });
});
it("transforme les erreurs en réponses loader sûres et conserve les statuts", () => {
  expect(failureStatus(httpFailure(404))).toBe(404);
  expect(failureStatus({ ok: false, kind: "network" })).toBe(503);
  expect(failureStatus({ ok: false, kind: "timeout" })).toBe(504);
  expect(() => requireApiData(httpFailure(500))).toThrow();
  expect(requireApiData({ ok: true, data: form })).toBe(form);
});
describe("configuration serveur", () => {
  it.each([
    undefined,
    "http://internal.invalid",
    "https://user:secret@example.com",
    "https://example.com/api",
    "https://example.com?secret=x",
  ])("refuse %s sans appel réseau", async (value) => {
    vi.stubEnv("API_BASE_URL", value);
    const transport = vi.fn<typeof fetch>();
    vi.stubGlobal("fetch", transport);
    expect(await getForm("1")).toEqual({ ok: false, kind: "configuration" });
    expect(transport).not.toHaveBeenCalled();
  });
  it("utilise l'origine exacte sans relayer les cookies ou en-têtes entrants", async () => {
    vi.stubEnv("API_BASE_URL", "https://backend-internal.invalid");
    const transport = vi
      .fn<typeof fetch>()
      .mockResolvedValue(Response.json(form));
    vi.stubGlobal("fetch", transport);
    expect((await getForm(form.id)).ok).toBe(true);
    expect(transport).toHaveBeenCalledWith(
      `https://backend-internal.invalid/api/v1/forms/${form.id}`,
      expect.objectContaining({
        headers: { Accept: "application/json" },
        credentials: "omit",
      }),
    );
  });
});

it("lit les nouvelles opérations avec leurs types générés et les IDs exacts", async () => {
  const { question, answers, stats } = await import(
    "../features/questions/fixtures.test-support"
  );
  const transport = vi
    .fn<typeof fetch>()
    .mockResolvedValueOnce(Response.json(question))
    .mockResolvedValueOnce(Response.json(answers))
    .mockResolvedValueOnce(Response.json(stats));
  const api = createPublicApi("", transport);
  expect(await api.getQuestion(question.id)).toEqual({
    ok: true,
    data: question,
  });
  expect(
    await api.getQuestionAnswers(question.id, {
      cursor: "opaque+/=",
      page_size: 20,
    }),
  ).toEqual({ ok: true, data: answers });
  expect(await api.getQuestionStats(question.id)).toEqual({
    ok: true,
    data: stats,
  });
  expect(transport).toHaveBeenNthCalledWith(
    2,
    `/api/v1/questions/${question.id}/answers?cursor=opaque%2B%2F%3D&page_size=20`,
    expect.objectContaining({ credentials: "omit", cache: "no-store" }),
  );
});
it("rejette des réponses incompatibles sans convertir les IDs numériques", async () => {
  const { question, answers, stats } = await import(
    "../features/questions/fixtures.test-support"
  );
  const transport = vi
    .fn<typeof fetch>()
    .mockResolvedValueOnce(Response.json({ ...question, id: 9007199254741022 }))
    .mockResolvedValueOnce(Response.json({ ...answers, next_cursor: null }))
    .mockResolvedValueOnce(
      Response.json({ ...stats, percentage_denominator: "persons" }),
    );
  const api = createPublicApi("", transport);
  for (const result of [
    await api.getQuestion(question.id),
    await api.getQuestionAnswers(question.id),
    await api.getQuestionStats(question.id),
  ])
    expect(result).toEqual({ ok: false, kind: "invalid_response" });
});

it("valide le nouveau contrat Formulaire et distingue indisponible de zéro", async () => {
  const value = {
    ...form,
    statistics_availability: {
      status: "available",
      generation_id: "generation-test",
      calculated_at: "2026-10-20T17:00:00Z",
      method_version: "historical-answers-v1",
    },
    questions_count: 1,
    questions: [
      {
        id: "9007199254740995",
        form_id: form.id,
        prompt: "Question ouverte",
        type: "text",
        position: 1,
        slug: "question",
        url: "/questions/9007199254740995-question",
        answers_count: 0,
        statistics: null,
      },
    ],
  };
  const transport = vi
    .fn<typeof fetch>()
    .mockResolvedValue(Response.json(value));
  expect(await createPublicApi("", transport).getForm(form.id)).toEqual({
    ok: true,
    data: value,
  });
  transport.mockResolvedValueOnce(
    Response.json({
      ...value,
      statistics_availability: { status: "unavailable" },
    }),
  );
  expect(await createPublicApi("", transport).getForm(form.id)).toEqual({
    ok: false,
    kind: "invalid_response",
  });
});
