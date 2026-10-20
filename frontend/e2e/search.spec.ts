import { expect, test } from "@playwright/test";

const origin = "http://127.0.0.1:4175";
const mock = "http://127.0.0.1:4176";
test.describe.configure({ mode: "serial" });
test.beforeEach(async ({ request }) => {
  await request.get(`${mock}/search-reset`);
});

for (const javaScriptEnabled of [true, false]) {
  test.describe(`Recherche SSR, JavaScript ${javaScriptEnabled ? "activé" : "désactivé"}`, () => {
    test.use({ javaScriptEnabled });
    test("recherche, contribution ancrée, retour, pagination et rechargement", async ({
      page,
      request,
    }) => {
      const initial = await page.goto(`${origin}/recherche`);
      expect(initial?.status()).toBe(200);
      expect(initial?.headers()["cache-control"]).toBe("private, no-store");
      expect(initial?.headers()["x-robots-tag"]).toBe("noindex, follow");
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(
        "Rechercher dans les paroles citoyennes",
      );
      await expect(page.getByRole("tab")).toHaveCount(0);
      await expect(
        page.getByText("Un point de départ pour écouter et comprendre"),
      ).toBeVisible();
      await page
        .getByLabel("Votre question ou votre sujet")
        .fill("école & lecture");
      expect(await (await request.get(`${mock}/search-calls`)).json()).toEqual(
        [],
      );
      await page
        .getByRole("button", { name: "Rechercher", exact: true })
        .click();
      await expect(
        page
          .getByRole("list", { name: "Réponses citoyennes", exact: true })
          .getByRole("listitem"),
      ).toHaveCount(20);
      await expect(page).toHaveURL(/cursor=first/);
      const firstUrl = page.url();
      await expect(page.getByText("Non", { exact: true })).toBeVisible();
      await expect(
        page.getByText("Autre proposition A", { exact: true }),
      ).toBeVisible();
      await expect(
        page.getByText("Autre proposition B", { exact: true }),
      ).toBeVisible();
      await expect(
        page.getByText("<script>alert('non fiable')</script>", {
          exact: false,
        }),
      ).toBeVisible();
      if (javaScriptEnabled)
        await page
          .locator("article")
          .first()
          .screenshot({ path: "/tmp/search-005-card.png" });
      const contribution = page
        .getByRole("link", { name: "Lire la contribution complète" })
        .first();
      await expect(contribution).toHaveAttribute(
        "href",
        /#answer-9007199254741993$/,
      );
      await contribution.click();
      await expect(page).toHaveURL(/#answer-9007199254741993$/);
      const anchor = page.locator("#answer-9007199254741993");
      await expect(anchor).toBeVisible();
      await expect
        .poll(async () => (await anchor.boundingBox())?.y)
        .toBeLessThan(250);
      await page.goBack();
      await expect(page).toHaveURL(firstUrl);
      await page
        .getByRole("link", { name: "Page suivante", exact: true })
        .click();
      await expect(
        page.getByText("Réponse du lot suivant.", { exact: true }),
      ).toBeVisible();
      await expect(
        page.getByRole("link", { name: "Page suivante", exact: true }),
      ).toHaveCount(0);
      await expect(
        page.getByText(/Vous êtes à la fin de cette sélection/),
      ).toBeVisible();
      await page.reload();
      await expect(
        page.getByText("Réponse du lot suivant.", { exact: true }),
      ).toBeVisible();
      await page
        .getByRole("link", { name: "Page précédente", exact: true })
        .click();
      await expect(page).toHaveURL(firstUrl);
      await page
        .getByRole("link", { name: "Page suivante", exact: true })
        .click();
      await page
        .getByRole("link", { name: "Première page", exact: true })
        .click();
      await expect(page).toHaveURL(firstUrl);
      const calls = await (await request.get(`${mock}/search-calls`)).json();
      expect(
        calls.filter((call: { calculated: boolean }) => call.calculated),
      ).toHaveLength(1);
      expect(
        calls.every((call: { path: string }) => call.path === "/api/v1/search"),
      ).toBe(true);
    });

    test("expiration explicite et relance manuelle, état vide et sources retirées", async ({
      page,
      request,
    }) => {
      await page.goto(`${origin}/recherche?q=expiration`);
      await expect(page).toHaveURL(/cursor=first/);
      await request.get(`${mock}/search-expire`);
      const response = await page.reload();
      expect(response?.status()).toBe(410);
      await expect(
        page.getByRole("heading", { name: "Cette sélection a expiré" }),
      ).toBeVisible();
      let calls = await (await request.get(`${mock}/search-calls`)).json();
      expect(
        calls.filter((call: { calculated: boolean }) => call.calculated),
      ).toHaveLength(1);
      await page
        .getByRole("button", { name: "Relancer la recherche", exact: true })
        .click();
      await expect(
        page.getByRole("list", { name: "Réponses citoyennes", exact: true }),
      ).toBeVisible();
      calls = await (await request.get(`${mock}/search-calls`)).json();
      expect(
        calls.filter((call: { calculated: boolean }) => call.calculated),
      ).toHaveLength(2);
      const empty = await page.goto(`${origin}/recherche?q=absent`);
      expect(empty?.status()).toBe(200);
      await expect(
        page.getByText(/Essayez de préciser votre sujet/),
      ).toBeVisible();
      const withdrawn = await page.goto(`${origin}/recherche?q=withdrawn`);
      expect(withdrawn?.status()).toBe(200);
      await expect(
        page.getByText(/Certaines réponses ne sont plus accessibles/),
      ).toBeVisible();
      await expect(
        page.getByText(/Les réponses de cette page ne sont plus consultables/),
      ).toBeVisible();
      await expect(
        page.getByText("Aucun résultat pour cette recherche.", { exact: true }),
      ).toHaveCount(0);
    });
  });
}

for (const status of [422, 500, 503, 504]) {
  test(`statut SSR ${status} et message public`, async ({ page }) => {
    const response = await page.goto(`${origin}/recherche?q=${status}`);
    expect(response?.status()).toBe(status);
    expect(response?.headers()["cache-control"]).toBe("private, no-store");
    expect(response?.headers()["x-robots-tag"]).toBe("noindex, follow");
    await expect(
      page.getByRole("region", { name: "Erreur de recherche" }),
    ).toBeVisible();
    expect(await page.content()).not.toMatch(/SECRET|private-host|private SQL/);
    await expect(
      page.getByRole("button", { name: "Réessayer", exact: true }),
    ).toBeVisible();
  });
}

test("validation sans ancien onglet ni filtre ignoré", async ({ page }) => {
  for (const params of [
    "q=test&tab=answers",
    "q=test&question_id=1",
    "q=test&page_size=21",
  ]) {
    const response = await page.goto(`${origin}/recherche?${params}`);
    expect(response?.status()).toBe(422);
  }
  await page.goto(`${origin}/recherche`);
  await expect(
    page.getByLabel("Votre question ou votre sujet"),
  ).toHaveAttribute("maxlength", "512");
});

test("petit écran, lecture agrandie et soumission au clavier", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await page.goto(`${origin}/recherche`);
  const field = page.getByLabel("Votre question ou votre sujet");
  await field.fill("mobilité rurale");
  await field.press("Enter");
  await expect(
    page.getByRole("list", { name: "Réponses citoyennes", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.evaluate(() => {
    document.documentElement.style.fontSize = "200%";
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

test("recherche obsolète annulée et nouvelle saisie sans attendre", async ({
  page,
}) => {
  await page.goto(`${origin}/recherche`);
  const field = page.getByLabel("Votre question ou votre sujet");
  await field.fill("slow");
  await field.press("Enter");
  await expect(
    page.getByText("Chargement en cours…", { exact: true }),
  ).toBeVisible();
  await field.fill("école");
  await field.press("Enter");
  await expect(
    page.getByRole("list", { name: "Réponses citoyennes", exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL(/q=%C3%A9cole/);
  await expect(field).toHaveValue("école");
});
