import { afterEach, expect, it, vi } from "vitest";
import { answers, catalog } from "../features/search/fixtures.test-support";
import { createPublicApi } from "./api";
import { searchAnswers, searchCatalog } from "./api.server";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});
it("encode accents, syntaxe et curseurs opaques, conserve les IDs et omet les cookies", async () => {
  const transport = vi
    .fn<typeof fetch>()
    .mockResolvedValueOnce(Response.json(answers))
    .mockResolvedValueOnce(Response.json(catalog));
  const api = createPublicApi("", transport);
  expect(
    await api.searchAnswers({
      q: 'école "lecture" OR -autre &',
      cursor: "page+2/=opaque",
    }),
  ).toEqual({ ok: true, data: answers });
  expect(
    await api.searchCatalog({
      q: "école",
      cursor_forms: "forms+2/=opaque",
      cursor_questions: "questions+2/=opaque",
    }),
  ).toEqual({ ok: true, data: catalog });
  expect(transport).toHaveBeenCalledTimes(2);
  expect(transport.mock.calls[0]?.[0]).toBe(
    `/api/v1/search/answers?${new URLSearchParams({ q: 'école "lecture" OR -autre &', cursor: "page+2/=opaque" })}`,
  );
  expect(transport.mock.calls[1]?.[0]).toBe(
    `/api/v1/search/catalog?${new URLSearchParams({ q: "école", cursor_forms: "forms+2/=opaque", cursor_questions: "questions+2/=opaque" })}`,
  );
  expect(transport.mock.calls[0]?.[1]).toMatchObject({
    credentials: "omit",
    cache: "no-store",
    method: "GET",
  });
});
it.each([422, 500, 503, 504])(
  "une erreur HTTP %i n'expose pas son corps",
  async (status) => {
    const transport = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        Response.json({ detail: "SQL SECRET http://private-host" }, { status }),
      );
    const response = await createPublicApi("", transport).searchAnswers({
      q: "école",
    });
    expect(response).toMatchObject({ ok: false, status });
    expect(JSON.stringify(response)).not.toMatch(/SECRET|SQL|private-host/);
  },
);
it("rejette du JSON malformé ou un modèle de recherche invalide", async () => {
  const transport = vi
    .fn<typeof fetch>()
    .mockResolvedValueOnce(
      new Response("{invalid", {
        headers: { "Content-Type": "application/json" },
      }),
    )
    .mockResolvedValueOnce(
      Response.json({
        ...answers,
        items: [{ ...answers.items[0], id: 9007199254741992 }],
      }),
    )
    .mockResolvedValueOnce(
      Response.json({
        ...catalog,
        has_next_questions: true,
        next_cursor_questions: null,
      }),
    );
  const api = createPublicApi("", transport);
  for (const call of [
    () => api.searchAnswers({ q: "école" }),
    () => api.searchAnswers({ q: "école" }),
    () => api.searchCatalog({ q: "école" }),
  ])
    expect(await call()).toEqual({ ok: false, kind: "invalid_response" });
});
it("les deux appels serveur utilisent la configuration privée existante", async () => {
  vi.stubEnv("API_BASE_URL", "http://127.0.0.1:4176");
  const transport = vi
    .fn<typeof fetch>()
    .mockResolvedValueOnce(Response.json(answers))
    .mockResolvedValueOnce(Response.json(catalog));
  vi.stubGlobal("fetch", transport);
  await searchAnswers({ q: answers.q });
  await searchCatalog({ q: catalog.q });
  expect(transport.mock.calls[0]?.[0]).toContain(
    "http://127.0.0.1:4176/api/v1/search/answers?",
  );
  expect(transport.mock.calls[1]?.[0]).toContain(
    "http://127.0.0.1:4176/api/v1/search/catalog?",
  );
});

it("annule les lectures de recherche et distingue délai et réseau", async () => {
  vi.useFakeTimers();
  try {
    const transport = vi
      .fn<typeof fetch>()
      .mockImplementation(
        (_url, options) =>
          new Promise((_resolve, reject) =>
            options?.signal?.addEventListener(
              "abort",
              () => reject(new DOMException("Aborted", "AbortError")),
              { once: true },
            ),
          ),
      );
    const api = createPublicApi("", transport);
    const controller = new AbortController();
    const cancelled = api.searchCatalog(
      { q: "école" },
      { signal: controller.signal },
    );
    controller.abort();
    expect(await cancelled).toEqual({ ok: false, kind: "cancelled" });
    const slow = api.searchAnswers({ q: "école" }, { timeoutMs: 20 });
    await vi.advanceTimersByTimeAsync(21);
    expect(await slow).toEqual({ ok: false, kind: "timeout" });
    transport.mockRejectedValueOnce(new TypeError("fetch failed SECRET"));
    expect(await api.searchAnswers({ q: "école" })).toEqual({
      ok: false,
      kind: "network",
    });
  } finally {
    vi.useRealTimers();
  }
});
