import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderToString } from "react-dom/server";
import { MemoryRouter, RouterContextProvider } from "react-router";
import { beforeEach, expect, it, vi } from "vitest";
import { question, stats } from "../features/questions/fixtures.test-support";
import { Statistics } from "../features/questions/statistics";
import { createPublicApi, type FormStatistics } from "../lib/api";
import { getFormStats } from "../lib/api.server";
import { loader } from "./dashboard";

vi.mock("../lib/api.server", () => ({ getFormStats: vi.fn() }));
vi.mock("../features/questions/stats-chart", () => ({
  default: () => <div data-testid="chart">Graphique</div>,
}));
beforeEach(() => vi.resetAllMocks());
const dashboard: FormStatistics = {
  form: question.form,
  questions: [
    { question: { ...question, type: "multi_choice" }, stats },
    {
      question: {
        ...question,
        id: "9007199254741023",
        type: "single_choice",
        position: null,
      },
      stats: {
        ...stats,
        question_id: "9007199254741023",
        type: "single_choice",
      },
    },
  ],
};
const args = () => ({
  request: new Request(`http://localhost/forms/${question.form.id}/dashboard`),
  url: new URL(`http://localhost/forms/${question.form.id}/dashboard`),
  params: { formId: question.form.id },
  context: new RouterContextProvider(),
  pattern: "/forms/:formId/dashboard",
});
it("utilise un seul appel serveur groupé et propage le signal", async () => {
  vi.mocked(getFormStats).mockResolvedValue({ ok: true, data: dashboard });
  const input = args();
  expect((await loader(input)).data).toEqual(dashboard);
  expect(getFormStats).toHaveBeenCalledExactlyOnceWith(question.form.id, {
    signal: input.request.signal,
  });
});
it.each([
  ["missing", 404],
  ["application", 500],
  ["unavailable", 503],
  ["server_timeout", 504],
] as const)("préserve le statut %s/%i", async (kind, status) => {
  vi.mocked(getFormStats).mockResolvedValue({ ok: false, kind, status });
  await expect(loader(args())).rejects.toMatchObject({
    init: {
      status,
      headers: {
        "Cache-Control": "private, no-store",
        "X-Robots-Tag": "noindex, nofollow",
      },
    },
  });
});
it("accepte un tableau de bord vide comme succès", async () => {
  vi.mocked(getFormStats).mockResolvedValue({
    ok: true,
    data: { ...dashboard, questions: [] },
  });
  expect((await loader(args())).data.questions).toEqual([]);
});
it("valide le contrat groupé, les BIGINT et les associations question/statistiques", async () => {
  const fetcher = vi
    .fn<typeof fetch>()
    .mockResolvedValueOnce(Response.json(dashboard))
    .mockResolvedValueOnce(
      Response.json({
        ...dashboard,
        questions: [
          { ...dashboard.questions[0], stats: { ...stats, question_id: "2" } },
        ],
      }),
    );
  const api = createPublicApi("", fetcher);
  expect(await api.getFormStats(question.form.id)).toEqual({
    ok: true,
    data: dashboard,
  });
  expect(fetcher.mock.calls[0]?.[0]).toBe(
    `/api/v1/forms/${question.form.id}/stats`,
  );
  expect(await api.getFormStats(question.form.id)).toEqual({
    ok: false,
    kind: "invalid_response",
  });
  expect(await api.getFormStats("bad")).toEqual({ ok: false, kind: "request" });
  expect(fetcher).toHaveBeenCalledTimes(2);
});
it("les tableaux complets sont dans le SSR, avec IDs uniques et sans graphique monté", () => {
  const html = renderToString(
    <MemoryRouter>
      {dashboard.questions.map((q) => (
        <Statistics
          key={q.question.id}
          stats={q.stats}
          deferChart
          headingLevel={3}
        />
      ))}
    </MemoryRouter>,
  );
  const document = new DOMParser().parseFromString(html, "text/html");
  expect(document.querySelectorAll("table")).toHaveLength(2);
  expect(document.querySelectorAll("h3")).toHaveLength(2);
  const ids = [...document.querySelectorAll("[id]")].map((node) => node.id);
  expect(new Set(ids).size).toBe(ids.length);
  expect(document.body.textContent).toContain("80 %");
  expect(document.body.textContent).toContain("50 %");
  expect(html).toContain("dépasser 100 %");
  expect(html).not.toContain('data-testid="chart"');
});
it("ne charge un graphique qu'après ouverture de son détail natif", async () => {
  render(<Statistics stats={stats} deferChart />);
  expect(screen.queryByTestId("chart")).toBeNull();
  await userEvent.click(screen.getByText("Afficher le graphique"));
  expect(await screen.findByTestId("chart")).toBeVisible();
  expect(screen.getByRole("table")).toBeVisible();
});
