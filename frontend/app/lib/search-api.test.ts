import { afterEach, expect, it, vi } from "vitest";
import { page } from "../features/search/fixtures.test-support";
import { createPublicApi } from "./api";
import { search } from "./api.server";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});
it("encode le langage naturel, les curseurs et conserve les BIGINT sans cookies", async () => {
  const transport = vi
    .fn<typeof fetch>()
    .mockResolvedValue(Response.json(page));
  const api = createPublicApi("", transport);
  const q = "école & lecture";
  expect(
    await api.search({ q, cursor: "page+2/=opaque", page_size: 20 }),
  ).toEqual({ ok: true, data: page });
  expect(transport.mock.calls[0]?.[0]).toBe(
    `/api/v1/search?${new URLSearchParams({ q, cursor: "page+2/=opaque", page_size: "20" })}`,
  );
  expect(transport.mock.calls[0]?.[1]).toMatchObject({
    credentials: "omit",
    cache: "no-store",
    method: "GET",
  });
});
it.each([410, 422, 500, 503, 504])(
  "erreur structurée %s sans exposer son message interne",
  async (status) => {
    const transport = vi.fn<typeof fetch>().mockResolvedValue(
      Response.json(
        {
          error: {
            code: status === 410 ? "search_expired" : "search_unavailable",
            message: "SQL SECRET http://private-host",
          },
        },
        { status },
      ),
    );
    const result = await createPublicApi("", transport).search({ q: "école" });
    expect(result).toMatchObject({ ok: false, status });
    expect(JSON.stringify(result)).not.toMatch(/SECRET|SQL|private-host/);
    if (status === 410)
      expect(result).toMatchObject({ kind: "expired", code: "search_expired" });
  },
);
it("rejette les modèles invalides, les liens falsifiés et les IDs numériques", async () => {
  for (const bad of [
    { ...page, items: [{ ...page.items[0], answer_id: 9007199254741992 }] },
    { ...page, items: [{ ...page.items[0], url: "https://private-host" }] },
    { ...page, has_next: true, next_cursor: null },
  ]) {
    const transport = vi
      .fn<typeof fetch>()
      .mockResolvedValue(Response.json(bad));
    expect(await createPublicApi("", transport).search()).toEqual({
      ok: false,
      kind: "invalid_response",
    });
  }
});
it("utilise l’origine privée côté serveur", async () => {
  vi.stubEnv("API_BASE_URL", "http://127.0.0.1:4176");
  const transport = vi
    .fn<typeof fetch>()
    .mockResolvedValue(Response.json(page));
  vi.stubGlobal("fetch", transport);
  await search({ q: page.q });
  expect(transport.mock.calls[0]?.[0]).toContain(
    "http://127.0.0.1:4176/api/v1/search?",
  );
});
it("distingue annulation, timeout et réseau", async () => {
  vi.useFakeTimers();
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
  const cancelled = api.search({ q: "école" }, { signal: controller.signal });
  controller.abort();
  expect(await cancelled).toEqual({ ok: false, kind: "cancelled" });
  const slow = api.search({ q: "école" }, { timeoutMs: 20 });
  await vi.advanceTimersByTimeAsync(21);
  expect(await slow).toEqual({ ok: false, kind: "timeout" });
  transport.mockRejectedValueOnce(new TypeError("SECRET"));
  expect(await api.search()).toEqual({ ok: false, kind: "network" });
});
