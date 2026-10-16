import { expect, test } from "@playwright/test";

const origin = "http://127.0.0.1:4175";
const formId = "9007199254740995";
const path = `/forms/${formId}/dashboard`;

test("HTML SSR : plusieurs questions ordonnées, tableaux, dénominateurs et canonical", async ({
  request,
}) => {
  const response = await request.get(`${origin}${path}`, {
    headers: { Cookie: "session_token=synthetic" },
  });
  expect(response.status()).toBe(200);
  const html = await response.text();
  expect(html).toContain("Statistiques — Participation citoyenne");
  expect(html).toContain(
    `rel="canonical" href="https://cahierdedoleances.fr${path}"`,
  );
  expect(html.match(/<table /g)).toHaveLength(2);
  expect(html).toMatch(/80(?:<!-- -->)? %/);
  expect(html).toMatch(/50(?:<!-- -->)? %/);
  expect(html).toMatch(/0(?:<!-- -->)? %/);
  expect(html).toContain("Autre texte");
  expect(html).toContain("dépasser 100 %");
  expect(html).toContain("réponses enregistrées");
  expect(html.indexOf("Quel mode de consultation")).toBeLessThan(
    html.indexOf("Quels sujets souhaitez"),
  );
  expect(html).not.toMatch(
    /127\.0\.0\.1:4176|recharts-surface|content="noindex/,
  );
  expect(response.headers()["cache-control"]).toBe("private, no-store");
  expect(response.headers()["set-cookie"]).toBeUndefined();
});

test("statuts HTTP réels, indisponibilité, état vide et absence de données sensibles", async ({
  request,
}) => {
  for (const status of [404, 500, 503, 504]) {
    const response = await request.get(`${origin}/forms/${status}/dashboard`);
    expect(response.status()).toBe(status);
    const html = await response.text();
    expect(html).toContain('content="noindex, nofollow"');
    expect(html).not.toMatch(/private SQL|SECRET|private-host/);
    expect(response.headers()["cache-control"]).toBe("private, no-store");
  }
  const unavailable = await request.get(`http://127.0.0.1:4177${path}`);
  expect(unavailable.status()).toBe(503);
  expect(await unavailable.text()).toContain("Service indisponible");
  const empty = await request.get(`${origin}/forms/9007199254740993/dashboard`);
  expect(empty.status()).toBe(200);
  expect(await empty.text()).toContain(
    "Ce formulaire ne contient aucune question statistique.",
  );
  expect((await request.get("http://127.0.0.1:4177/")).status()).toBe(200);
});

test("parcours Enquêtes → Formulaire → Dashboard → Question, focus et hydratation", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  let charts = 0;
  page.on("request", (request) => {
    if (request.url().includes("stats-chart")) charts++;
  });
  await page.goto(`${origin}/enquetes`);
  await page.getByRole("link", { name: "Participation citoyenne" }).click();
  await page.getByRole("link", { name: "Voir le tableau de bord" }).click();
  await expect(page).toHaveURL(`${origin}${path}`);
  await expect(page.getByRole("table")).toHaveCount(2);
  expect(charts).toBe(0);
  await expect(page.locator(".recharts-surface")).toHaveCount(0);
  const summaries = page.locator("summary");
  await summaries.first().focus();
  await expect(summaries.first()).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator(".recharts-surface")).toHaveCount(1);
  expect(charts).toBe(1);
  await summaries.nth(1).click();
  await expect(page.locator(".recharts-surface")).toHaveCount(2);
  expect(charts).toBe(1);
  await expect(page.getByRole("table")).toHaveCount(2);
  const ids = await page
    .locator("[id]")
    .evaluateAll((nodes) => nodes.map((node) => node.id));
  expect(new Set(ids).size).toBe(ids.length);
  await page
    .getByRole("link", { name: "Quels sujets souhaitez-vous aborder ?" })
    .click();
  await expect(page).toHaveURL(`${origin}/questions/9007199254741021-sujets`);
  await page.goBack();
  await expect(page).toHaveURL(`${origin}${path}`);
  await page.getByRole("link", { name: "← Retour au formulaire" }).click();
  await expect(page).toHaveURL(`${origin}/forms/${formId}`);
  await page.goto(`${origin}/forms/9007199254740993`);
  await expect(
    page.getByRole("link", { name: "Voir le tableau de bord" }),
  ).toHaveCount(0);
  expect(errors).toEqual([]);
});

test("mobile, zoom 200 %, liens clavier et absence de débordement", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await page.goto(`${origin}${path}`);
  await page.keyboard.press("Tab");
  await page
    .getByRole("link", { name: "Aller au contenu principal" })
    .press("Enter");
  await expect(page.getByRole("main")).toBeFocused();
  await page.locator("summary").first().click();
  await expect(page.locator(".recharts-surface")).toHaveCount(1);
  await page.evaluate(() => {
    document.documentElement.style.zoom = "2";
  });
  expect(
    await page.evaluate(
      () =>
        document.documentElement.scrollWidth <=
        document.documentElement.clientWidth,
    ),
  ).toBe(true);
  await expect(page.getByRole("table").first()).toBeVisible();
});

test("sans JavaScript : navigation et tableaux statistiques complets", async ({
  browser,
}) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto(`${origin}/enquetes`);
  await page.getByRole("link", { name: "Participation citoyenne" }).click();
  await page.getByRole("link", { name: "Voir le tableau de bord" }).click();
  await expect(page.getByRole("table")).toHaveCount(2);
  await expect(
    page.getByRole("cell", { name: "80 %", exact: true }),
  ).toHaveCount(2);
  await page
    .getByRole("link", { name: "Quel mode de consultation privilégier ?" })
    .click();
  await expect(page).toHaveURL(
    `${origin}/questions/9007199254741020-consultation`,
  );
  await expect(page.getByRole("table")).toBeVisible();
  await context.close();
});
