import { expect, test } from "@playwright/test";

const origin = "http://127.0.0.1:4175";
const mock = "http://127.0.0.1:4176";
const formId = "9007199254740995";
const path = `/forms/${formId}`;

test("HTML initial : toutes les questions, graphiques et tableaux ; un seul appel Formulaire", async ({
  request,
}) => {
  await request.get(`${mock}/forms-reset`);
  const response = await request.get(`${origin}/forms/101`, {
    headers: { Cookie: "session_token=synthetic" },
  });
  expect(response.status()).toBe(200);
  const html = await response.text();
  expect(html).toContain(
    `rel="canonical" href="https://cahierdedoleances.fr/forms/101"`,
  );
  expect(html).not.toContain("Sommaire des questions");
  expect(html).not.toContain("Retour au sommaire");
  expect(html.match(/data-chart-kind=/g)).toHaveLength(2);
  expect(html.match(/<table /g)).toHaveLength(2);
  expect(html).toContain("Plusieurs réponses possibles");
  expect(html).toContain("Autre texte");
  expect(html).not.toMatch(
    /recharts|<svg|Afficher le graphique|Voir le tableau de bord/,
  );
  expect(response.headers()["cache-control"]).toBe("private, no-store");
  expect(response.headers()["set-cookie"]).toBeUndefined();
  const calls = await (await request.get(`${mock}/forms-calls`)).json();
  expect(
    calls.filter((value: string) => value === "/api/v1/forms/101"),
  ).toEqual(["/api/v1/forms/101"]);
});

test("ancien Dashboard : 308 serveur sans requête API, même en cas d'API indisponible", async ({
  request,
}) => {
  await request.get(`${mock}/forms-reset`);
  for (const base of [origin, "http://127.0.0.1:4177"]) {
    const response = await request.get(
      `${base}/forms/999991/dashboard?contrib=2`,
      {
        maxRedirects: 0,
      },
    );
    expect(response.status()).toBe(308);
    expect(response.headers().location).toBe(`/forms/999991?contrib=2`);
  }
  expect(
    (await (await request.get(`${mock}/forms-calls`)).json()).filter(
      (value: string) => value.includes("999991"),
    ),
  ).toEqual([]);
});

for (const javaScriptEnabled of [true, false]) {
  test.describe(`formulaire continu, JS ${javaScriptEnabled}`, () => {
    test.use({ javaScriptEnabled });
    test("titres cliquables, détails au clavier, page Question, retour et ancienne ancre", async ({
      page,
    }) => {
      const errors: string[] = [];
      const charts: string[] = [];
      page.on("pageerror", (e) => errors.push(e.message));
      page.on("request", (r) => {
        if (r.url().includes("stats-chart")) charts.push(r.url());
      });
      await page.goto(`${origin}/enquetes`);
      await page
        .getByRole("link", { name: "Participation citoyenne", exact: true })
        .click();
      await expect(page).toHaveURL(`${origin}${path}`);
      await expect(page.locator("[data-chart-kind]")).toHaveCount(2);
      await expect(page.locator("h1")).toHaveCSS("color", "rgb(0, 0, 0)");
      await expect(page.locator("section h2 a").first()).toHaveCSS(
        "color",
        "rgb(0, 0, 0)",
      );
      await page.goto(`${origin}${path}#question-9007199254741021`);
      const target = page.locator("#question-9007199254741021");
      await expect(page).toHaveURL(/#question-9007199254741021$/);
      await expect
        .poll(async () => (await target.boundingBox())?.y)
        .toBeLessThan(100);
      const details = target.locator("details");
      await expect(details).not.toHaveAttribute("open");
      const summary = details.locator("summary");
      await summary.focus();
      await page.keyboard.press("Enter");
      await expect(details).toHaveAttribute("open", "");
      await expect(details.getByRole("table")).toBeVisible();
      await target.locator("h2 a").click();
      await expect(page).toHaveURL(
        `${origin}/questions/9007199254741021-sujets`,
      );
      await page.locator("summary").click();
      await expect(page.getByRole("table")).toBeVisible();
      await page.goBack();
      await expect(page).toHaveURL(/#question-9007199254741021$/);
      // Reset the observation: Recharts is still intentionally used by individual Questions.
      charts.length = 0;
      await page.goto(`${origin}${path}/dashboard#question-9007199254741020`);
      await expect(page).toHaveURL(
        `${origin}${path}#question-9007199254741020`,
      );
      await expect
        .poll(
          async () =>
            (await page.locator("#question-9007199254741020").boundingBox())?.y,
        )
        .toBeLessThan(100);
      expect(charts).toEqual([]);
      expect(errors).toEqual([]);
    });
    test("Oui/Non, répartition incomplète, zéro et statistiques indisponibles", async ({
      page,
    }) => {
      await page.goto(`${origin}/forms/101`);
      await expect(page.locator('[data-chart-kind="yes-no"]')).toHaveCount(1);
      await expect(page.getByText("7 · 70 %", { exact: true })).toBeVisible();
      await page.goto(`${origin}/forms/104`);
      await expect(page.locator('[data-chart-kind="yes-no"]')).toHaveCount(0);
      await expect(page.getByText("4 · 40 %", { exact: true })).toBeVisible();
      await page.goto(`${origin}/forms/103`);
      await expect(
        page.getByText("Aucune réponse enregistrée pour cette question.", {
          exact: true,
        }),
      ).toBeVisible();
      await expect(page.getByText("0 · 0 %", { exact: true })).toHaveCount(3);
      await page.goto(`${origin}/forms/102`);
      await expect(
        page.getByText(
          /Les résultats statistiques sont momentanément indisponibles/,
        ),
      ).toBeVisible();
      await expect(page.locator("[data-chart-kind]")).toHaveCount(0);
      await expect(
        page.getByText("0 réponses enregistrées", { exact: true }),
      ).toHaveCount(0);
      await expect(page.locator("section h2 a").first()).toBeVisible();
    });
  });
}

test("37 questions, largeur 320 px et zoom texte 200 % sans débordement", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await page.goto(`${origin}/forms/105`);
  await expect(
    page
      .getByRole("list", { name: "Questions du formulaire" })
      .getByRole("heading"),
  ).toHaveCount(37);
  await expect(
    page.getByRole("navigation", { name: "Sommaire des questions" }),
  ).toHaveCount(0);
  const lastId = await page
    .locator('section[id^="question-"]')
    .last()
    .getAttribute("id");
  await page.goto(`${origin}/forms/105#${lastId}`);
  await expect(
    page.locator('section[id^="question-"]').last().getByRole("heading"),
  ).toBeInViewport();
  await page.goto(`${origin}/forms/101`);
  await page.locator("summary").first().click();
  await page.evaluate(() => {
    document.documentElement.style.fontSize = "200%";
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({ path: "/tmp/forms-003-mobile.png", fullPage: false });
});

test("impression et couleurs forcées : libellés et détails restent lisibles", async ({
  page,
}) => {
  await page.goto(`${origin}/forms/101`);
  await page.emulateMedia({ forcedColors: "active" });
  await expect(page.getByText("7 · 70 %", { exact: true })).toBeVisible();
  await page.emulateMedia({ media: "print", forcedColors: "none" });
  await expect(
    page
      .locator("details")
      .first()
      .getByText("Contributions distinctes ayant répondu", { exact: true }),
  ).toBeVisible();
  await page.pdf({
    path: "/tmp/forms-003-print.pdf",
    format: "A4",
    printBackground: true,
  });
});

for (const javaScriptEnabled of [true, false]) {
  test.describe(`contributions du questionnaire, JS ${javaScriptEnabled}`, () => {
    test.use({ javaScriptEnabled });
    test("deux boutons, lecture et navigation précédente/suivante", async ({
      page,
    }) => {
      await page.goto(`${origin}${path}`);
      const buttons = page.getByRole("link", {
        name: "Voir les contributions à ce questionnaire",
        exact: true,
      });
      await expect(buttons).toHaveCount(2);
      await expect(buttons.first()).toHaveAttribute(
        "href",
        `${path}/contributions`,
      );
      await buttons.first().click();
      await expect(
        page.getByRole("list", { name: "Réponses de la contribution" }),
      ).toBeVisible();
      await expect(
        page.getByRole("link", {
          name: "← Contribution précédente",
          exact: true,
        }),
      ).toHaveCount(0);
      await page
        .getByRole("link", { name: "Contribution suivante →", exact: true })
        .first()
        .click();
      await expect(page).toHaveURL(`${origin}${path}/contributions?contrib=2`);
      await page
        .getByRole("link", { name: "Contribution suivante →", exact: true })
        .first()
        .click();
      await expect(
        page.getByRole("link", {
          name: "Contribution suivante →",
          exact: true,
        }),
      ).toHaveCount(0);
      await page
        .getByRole("link", { name: "← Contribution précédente", exact: true })
        .first()
        .click();
      await expect(page).toHaveURL(`${origin}${path}/contributions?contrib=2`);
    });
  });
}
