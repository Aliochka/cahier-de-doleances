import { expect, test } from "@playwright/test";

const origin = "http://127.0.0.1:4175";
const authorPath = "/authors/9007199254743993";
const formPath = "/forms/9007199254740995";
const contributionPath = `${formPath}/contributions/9007199254742993`;
const questionPath = "/questions/9007199254741022-participation";
const targetId = "answer-9007199254741992";

test("SSR auteur et contribution : contenu essentiel, métadonnées, anonymat et ancres", async ({
  request,
}) => {
  for (const path of [authorPath, contributionPath]) {
    const response = await request.get(`${origin}${path}`, {
      headers: { Cookie: "session_token=synthetic" },
    });
    expect(response.status()).toBe(200);
    const html = await response.text();
    expect(html).toContain("Auteur anonyme");
    expect(html).toContain('name="description"');
    expect(html).toContain(
      `rel="canonical" href="https://cahierdedoleances.fr${path}"`,
    );
    expect(response.headers()["cache-control"]).toBe("private, no-store");
    expect(response.headers()["set-cookie"]).toBeUndefined();
    expect(html).not.toContain("127.0.0.1:4176");
    expect(html).not.toContain("?contrib=");
    if (path === authorPath) {
      expect(html).toContain(`${formPath}/contributions/9007199254742994`);
      expect(html).toContain("Afficher davantage de contributions");
    } else {
      expect(html).toContain(`id="${targetId}"`);
      expect(html).toContain("&lt;script&gt;");
      expect(html).toContain("Consultations citoyennes");
      expect(html).toContain("Autre proposition");
      expect(html).toContain("42");
    }
  }
});

test("statuts réels, formulaire incorrect, panne API et erreur partielle auteur", async ({
  request,
}) => {
  for (const status of [404, 500, 503, 504]) {
    for (const path of [
      `/authors/${status}`,
      `${formPath}/contributions/${status}`,
    ]) {
      const response = await request.get(`${origin}${path}`);
      expect(response.status()).toBe(status);
      expect(response.headers()["x-robots-tag"]).toContain("noindex");
      const html = await response.text();
      expect(html).not.toContain("private SQL");
      expect(html).not.toContain('rel="canonical"');
    }
  }
  expect(
    (
      await request.get(`${origin}/forms/42/contributions/9007199254742993`)
    ).status(),
  ).toBe(404);
  for (const path of [authorPath, contributionPath]) {
    const response = await request.get(`http://127.0.0.1:4177${path}`);
    expect(response.status()).toBe(503);
    expect(await response.text()).toContain("Service indisponible");
  }
  const partial = await request.get(`${origin}/authors/102`);
  expect(partial.status()).toBe(503);
  expect(await partial.text()).toContain("Pseudonyme public");
  expect((await request.get("http://127.0.0.1:4177/")).status()).toBe(200);
});

test("navigation auteur, lots successifs, contribution et formulaire", async ({
  page,
}) => {
  await page.goto(`${origin}${authorPath}`);
  await expect(
    page.getByRole("link", { name: /Consulter la contribution/ }),
  ).toHaveCount(2);
  await page
    .getByRole("link", { name: "Afficher davantage de contributions" })
    .click();
  await expect(page).toHaveURL(
    `${origin}${authorPath}?after_id=9007199254742994`,
  );
  await expect(page.getByRole("heading", { level: 3 })).toHaveCount(2);
  await page.getByRole("link", { name: "Revenir au début" }).click();
  const link = page.getByRole("link", {
    name: "Consulter la contribution 9007199254742993",
  });
  await link.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(`${origin}${contributionPath}`);
  await page.getByRole("link", { name: "Auteur anonyme", exact: true }).click();
  await expect(page).toHaveURL(`${origin}${authorPath}`);
  await page.goBack();
  await page.getByRole("link", { name: /Retour au formulaire/ }).click();
  await expect(page).toHaveURL(`${origin}${formPath}`);
  await page.goto(`${origin}/authors/100`);
  await expect(
    page.getByText("Aucune contribution consultable dans ce lot."),
  ).toBeVisible();
  await page.goto(`${origin}${formPath}/contributions/9007199254742995`);
  await expect(page.getByText("Auteur non renseigné")).toBeVisible();
  await expect(
    page.getByText(
      "Cette contribution ne contient aucune réponse consultable.",
    ),
  ).toBeVisible();
});

test("ancre directe sans JavaScript, texte complet et pagination auteur", async ({
  browser,
}) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto(`${origin}${contributionPath}#${targetId}`);
  const target = page.locator(`#${targetId}`);
  await expect(target).toBeVisible();
  await expect(target).toHaveCSS("outline-style", "solid");
  const rect = await target.boundingBox();
  expect(rect?.y).toBeGreaterThanOrEqual(0);
  expect(rect?.y).toBeLessThan(400);
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute(
    "href",
    `https://cahierdedoleances.fr${contributionPath}`,
  );
  await expect(
    page
      .getByRole("list", { name: "Réponses de la contribution" })
      .getByRole("heading", { level: 2 }),
  ).toHaveCount(4);
  await expect(page.locator("main script")).toHaveCount(0);
  await page.goto(`${origin}${authorPath}`);
  await page
    .getByRole("link", { name: "Afficher davantage de contributions" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Formulaire synthétique" }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Consulter la contribution 9007199254742996" })
    .click();
  await expect(
    page.getByText(
      "Cette contribution ne contient aucune réponse consultable.",
    ),
  ).toBeVisible();
  await context.close();
});

test("question vers contribution ciblée, arrière, focus et hydratation", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  await page.goto(`${origin}${questionPath}?cursor=page%2B2%2F%3Dopaque`);
  const link = page.getByRole("link", {
    name: "Voir la contribution complète",
  });
  await link.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(`${origin}${contributionPath}#${targetId}`);
  const target = page.locator(`#${targetId}`);
  await expect(target).toHaveCSS("outline-style", "solid");
  await expect(target).toBeFocused();
  await page.goBack();
  await expect(page).toHaveURL(
    `${origin}${questionPath}?cursor=page%2B2%2F%3Dopaque`,
  );
  await page.goto(`${origin}${contributionPath}#${targetId}`);
  await target.getByRole("link").click();
  await expect(page).toHaveURL(`${origin}${questionPath}`);
  expect(errors).toEqual([]);
});

test("mobile et zoom 200 % sans débordement", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 740 });
  for (const path of [authorPath, contributionPath]) {
    await page.goto(`${origin}${path}`);
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
  }
});

for (const javaScriptEnabled of [true, false]) {
  test.describe(`présentation contribution JS ${javaScriptEnabled}`, () => {
    test.use({ javaScriptEnabled });
    test("titres noirs et champs structurés sans copie textuelle", async ({
      page,
    }) => {
      await page.goto(`${origin}${contributionPath}`);
      await expect(page.locator("h1")).toHaveCSS("color", "rgb(0, 0, 0)");
      await expect(page.locator("section h2 a").first()).toHaveCSS(
        "color",
        "rgb(0, 0, 0)",
      );
      const answer = page.locator("#answer-9007199254741994");
      await expect(
        answer.getByText("Consultations citoyennes", { exact: true }),
      ).toHaveCount(1);
      await expect(answer.locator(":scope > p")).toHaveCount(1);
      await expect(
        answer.getByText("Autre : Autre proposition", { exact: true }),
      ).toBeVisible();
    });
  });
}
