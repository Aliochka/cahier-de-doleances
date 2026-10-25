import { expect, test } from "@playwright/test";

test.use({ timezoneId: "Pacific/Kiritimati" });

const origin = "http://127.0.0.1:4175";
const text = "/questions/9007199254741022-participation";
const single = "/questions/9007199254741020-consultation";
const multiple = "/questions/9007199254741021-sujets";

// These tests exercise real SSR HTTP responses against a loopback-only synthetic API.
test("SSR fournit les textes, les tableaux, les métadonnées et les identifiants sans JavaScript", async ({
  request,
}) => {
  for (const path of [text, single, multiple]) {
    const response = await request.get(`${origin}${path}`);
    expect(response.status()).toBe(200);
    const html = await response.text();
    expect(html).toContain('name="description"');
    expect(html).toContain(
      `rel="canonical" href="https://cahierdedoleances.fr${path}"`,
    );
    expect(html).toContain("Participation citoyenne");
    expect(html).not.toContain("127.0.0.1:4176");
    expect(response.headers()["cache-control"]).toBe("private, no-store");
    expect(response.headers()["set-cookie"]).toBeUndefined();
    if (path === text) {
      expect(html).toContain("Une réponse citoyenne.\n\nUn second paragraphe.");
      expect(html).toContain("&lt;script&gt;");
      expect(html).toContain("Auteur anonyme");
      expect(html).toContain("cursor=page%2B2%2F%3Dopaque");
    } else {
      expect(html).toContain("<table");
      expect(html).toContain("Option sans sélection");
      expect(html).toContain("Autre texte");
      expect(html).not.toContain("recharts-surface");
    }
  }
});

test("liens à curseur sans JavaScript, ordre, fin et retour au premier lot", async ({
  browser,
}) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto(`${origin}${text}`);
  await expect(
    page.getByText("Une réponse citoyenne.", { exact: false }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Afficher davantage de réponses" })
    .click();
  await expect(page).toHaveURL(`${origin}${text}?cursor=page%2B2%2F%3Dopaque`);
  await expect(page.getByText("Réponse du lot suivant.")).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Afficher davantage de réponses" }),
  ).toHaveCount(0);
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute(
    "content",
    "noindex, follow",
  );
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute(
    "href",
    `https://cahierdedoleances.fr${text}?cursor=page%2B2%2F%3Dopaque`,
  );
  await page.getByRole("link", { name: "Revenir au début" }).click();
  await expect(
    page.getByText("Une réponse citoyenne.", { exact: false }),
  ).toBeVisible();
  await page.goto(`${origin}${multiple}`);
  await page.locator("summary").click();
  await expect(page.getByRole("table")).toBeVisible();
  await expect(
    page.getByText(/Plusieurs sélections sont possibles/),
  ).toBeVisible();
  await context.close();
});

test("canonicalisation historique et véritables statuts HTTP du détail et des erreurs partielles", async ({
  request,
}) => {
  for (const key of ["9007199254741022-ancien", "9007199254741022"]) {
    const response = await request.get(
      `${origin}/questions/${key}?cursor=opaque`,
      { maxRedirects: 0 },
    );
    expect(response.status()).toBe(308);
    expect(response.headers().location).toBe(`${text}?cursor=opaque`);
  }
  for (const status of [404, 500, 503, 504]) {
    const response = await request.get(`${origin}/questions/${status}-exemple`);
    expect(response.status()).toBe(status);
    expect(response.headers()["x-robots-tag"]).toContain("noindex");
    expect(await response.text()).not.toContain("private SQL");
  }
  for (const path of [
    "/questions/101-exemple?cursor=fail",
    "/questions/102-exemple",
  ]) {
    const response = await request.get(`${origin}${path}`);
    expect(response.status()).toBe(503);
    expect(response.headers()["cache-control"]).toBe("private, no-store");
    const html = await response.text();
    expect(html).toContain("Comment améliorer la participation citoyenne");
    expect(html).toContain("momentanément indisponible");
    expect(html).not.toContain("private SQL");
    expect(html).not.toContain("<table");
  }
  expect((await request.get(`${origin}${text}?cursor=`)).status()).toBe(422);
  expect((await request.get(`http://127.0.0.1:4177${text}`)).status()).toBe(
    503,
  );
});

test("parcours au clavier, retour arrière et hydratation des graphiques", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  await page.goto(`${origin}/forms/9007199254740995`);
  const link = page.locator("#question-9007199254741021 h2 a");
  await link.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(`${origin}${multiple}`);
  await expect(
    page
      .getByRole("region", { name: "Résultats de la question", exact: true })
      .locator("[data-chart-kind]"),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Réponses « Autre » à la question" }),
  ).toBeVisible();
  await expect(
    page.getByText("Une autre proposition citoyenne."),
  ).toBeVisible();
  await page.locator("summary").focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("table").getByRole("row")).toHaveCount(5);
  await page.getByRole("link", { name: /Retour au formulaire/ }).click();
  await expect(page).toHaveURL(`${origin}/forms/9007199254740995`);
  await page.goBack();
  await expect(page).toHaveURL(`${origin}${multiple}`);
  await expect(
    page
      .getByRole("region", { name: "Résultats de la question", exact: true })
      .locator("[data-chart-kind]"),
  ).toBeVisible();
  await page.goto(`${origin}${text}?cursor=page%2B2%2F%3Dopaque`);
  await expect(page.locator("time")).toHaveText("15 janvier 2019");
  await page.getByRole("link", { name: "Revenir au début" }).click();
  await expect(
    page.getByText("Une réponse citoyenne.", { exact: false }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("une erreur de lot préserve les réponses consultées et la navigation reste disponible", async ({
  page,
}) => {
  const requests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/questions/101-exemple.data"))
      requests.push(request.url());
  });
  await page.goto(`${origin}/questions/101-exemple`);
  await expect(
    page.getByText("Une réponse citoyenne.", { exact: false }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Afficher davantage de réponses" })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "momentanément indisponible",
  );
  await expect(
    page.getByText("Le lot précédemment consulté reste affiché ci-dessous."),
  ).toBeVisible();
  await expect(
    page.getByText("Une réponse citoyenne.", { exact: false }),
  ).toBeVisible();
  expect(requests).toHaveLength(1);
  await page.getByRole("button", { name: "Réessayer" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect.poll(() => requests.length).toBe(2);
  await page.goBack();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await page.goto(`${origin}/questions/100-exemple`);
  await expect(
    page.getByText("Aucune réponse consultable dans ce lot."),
  ).toBeVisible();
});

test("mobile et zoom 200 % : textes, tableau et graphique sans débordement", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 740 });
  for (const path of [text, single, multiple]) {
    await page.goto(`${origin}${path}`);
    if (path !== text)
      await expect(page.locator("[data-chart-kind]")).toBeVisible();
    await page.evaluate(() => {
      document.documentElement.style.zoom = "2";
    });
    await expect
      .poll(() =>
        page.evaluate(
          () =>
            document.documentElement.scrollWidth <=
            document.documentElement.clientWidth,
        ),
      )
      .toBe(true);
  }
});
