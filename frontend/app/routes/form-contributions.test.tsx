import { RouterContextProvider } from "react-router";
import { beforeEach, expect, it, vi } from "vitest";
import { contribution } from "../features/contributions/fixtures.test-support";
import { getFormContribution } from "../lib/api.server";
import { loader } from "./form-contributions";

vi.mock("../lib/api.server", () => ({ getFormContribution: vi.fn() }));
beforeEach(() => vi.resetAllMocks());
const args = (query = "") => ({
  request: new Request(
    `http://localhost/forms/${contribution.form.id}/contributions${query}`,
  ),
  url: new URL(
    `http://localhost/forms/${contribution.form.id}/contributions${query}`,
  ),
  params: { formId: contribution.form.id },
  context: new RouterContextProvider(),
  pattern: "/forms/:formId/contributions",
});
it("résout le premier rang et propose le suivant sans confondre rang et BIGINT", async () => {
  vi.mocked(getFormContribution)
    .mockResolvedValueOnce({
      ok: true,
      data: { ...contribution, legacy_index: "1" },
    })
    .mockResolvedValueOnce({
      ok: true,
      data: {
        ...contribution,
        contribution: { ...contribution.contribution, id: "9007199254742994" },
        legacy_index: "2",
      },
    });
  const input = args();
  const result = await loader(input);
  if (result instanceof Response) throw new Error("Unexpected redirect");
  expect(result.data.navigation).toEqual({
    previous: null,
    next: `/forms/${contribution.form.id}/contributions?contrib=2`,
  });
  expect(getFormContribution).toHaveBeenNthCalledWith(
    1,
    contribution.form.id,
    "1",
    { signal: input.request.signal },
  );
});
it("le dernier rang ne propose pas de suivant lorsque l'API borne le rang", async () => {
  vi.mocked(getFormContribution).mockResolvedValue({
    ok: true,
    data: { ...contribution, legacy_index: "3" },
  });
  const result = await loader(args("?contrib=3"));
  if (result instanceof Response) throw new Error("Unexpected redirect");
  expect(result.data.navigation.next).toBeNull();
  expect(result.data.navigation.previous).toContain("contrib=2");
});
it("un rang hors plage redirige vers le rang réellement résolu", async () => {
  vi.mocked(getFormContribution).mockResolvedValue({
    ok: true,
    data: { ...contribution, legacy_index: "3" },
  });
  const result = await loader(args("?contrib=99"));
  expect(result).toBeInstanceOf(Response);
  if (result instanceof Response)
    expect(result.headers.get("Location")).toContain("contrib=3");
  expect(getFormContribution).toHaveBeenCalledTimes(1);
});
it.each(["0", "-1", "abc", "9223372036854775808"])(
  "rejette le rang %s avant tout appel",
  async (value) => {
    await expect(loader(args(`?contrib=${value}`))).rejects.toMatchObject({
      status: 422,
    });
    expect(getFormContribution).not.toHaveBeenCalled();
  },
);
