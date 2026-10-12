import { expect, test } from "@playwright/test";

const origin = "http://127.0.0.1:4175";
const api = "http://127.0.0.1:4176";
const formId = "9007199254740995";
const questionPath = "/questions/9007199254741022-participation";
const path = (q: string, tab = "answers", extra: Record<string, string> = {}) =>
  `/recherche?${new URLSearchParams({ q, tab, ...extra })}`;

for (const tab of ["answers", "catalog"]) {
  test(`SSR ${tab} : contenu, métadonnées, confidentialité et HTML sans hydratation`, async ({
    request,
  }) => {
    const q = `SSR-${tab}`;
    const response = await request.get(`${origin}${path(q, tab)}`, {
      headers: {
        Cookie: "session_token=synthetic",
        "X-Forwarded-Host": "private-host",
      },
    });
    expect(response.status()).toBe(200);
    const html = await response.text();
    expect(html).toContain("Participation citoyenne");
    expect(html).toContain('content="noindex, follow"');
    expect(html).toContain(
      'rel="canonical" href="https://cahierdedoleances.fr/recherche"',
    );
    expect(html).toContain("<title>Recherche — Cahier de doléances</title>");
    expect(html).toContain('name="description"');
    expect(html).not.toMatch(/private-host|127\.0\.0\.1:4176|session_token/);
    expect(response.headers()["cache-control"]).toBe("private, no-store");
    expect(response.headers()["x-robots-tag"]).toBe("noindex, follow");
    expect(response.headers()["set-cookie"]).toBeUndefined();
    if (tab === "answers") {
      expect(html).toContain(
        `href="/forms/${formId}/contributions/9007199254742993#answer-9007199254741993"`,
      );
      expect(html).toContain("&lt;script&gt;");
    } else expect(html).toContain(`href="${questionPath}"`);
    const calls: { path: string; query: string }[] = await (
      await request.get(`${api}/search-calls`)
    ).json();
    expect(
      calls.filter((call) => new URLSearchParams(call.query).get("q") === q),
    ).toEqual([
      {
        path: `/api/v1/search/${tab}`,
        query: `?${new URLSearchParams({ q })}`,
      },
    ]);
  });
}

test("formulaire, Entrée, bouton, brouillon et onglets : URL source de vérité et appels indépendants", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(`${origin}/recherche`);
  const input = page.getByLabel("Mots-clés");
  const q = 'école & "lecture" OR -autre';
  await input.fill(q);
  await page.waitForTimeout(250);
  const callsBefore: { query: string }[] = await (
    await request.get(`${api}/search-calls`)
  ).json();
  expect(
    callsBefore.filter((c) => new URLSearchParams(c.query).get("q") === q),
  ).toHaveLength(0);
  await input.press("Enter");
  await expect(page).toHaveURL(`${origin}${path(q)}`);
  await expect(
    page.getByRole("list", { name: "Résultats Réponses" }),
  ).toBeVisible();
  await input.fill("brouillon non soumis");
  await page
    .getByRole("link", { name: "Questions et enquêtes", exact: true })
    .click();
  await expect(page).toHaveURL(`${origin}${path(q, "catalog")}`);
  await expect(input).toHaveValue("brouillon non soumis");
  await expect(
    page.getByRole("link", { name: "Questions et enquêtes", exact: true }),
  ).toHaveAttribute("aria-current", "page");
  const calls: { path: string; query: string }[] = await (
    await request.get(`${api}/search-calls`)
  ).json();
  expect(
    calls
      .filter((c) => new URLSearchParams(c.query).get("q") === q)
      .map((c) => c.path),
  ).toEqual(["/api/v1/search/answers", "/api/v1/search/catalog"]);
  await input.fill("nouvelle recherche");
  await page.getByRole("button", { name: "Rechercher", exact: true }).click();
  await expect(page).toHaveURL(
    `${origin}${path("nouvelle recherche", "catalog")}`,
  );
  await page.goBack();
  await expect(page).toHaveURL(`${origin}${path(q, "catalog")}`);
  await expect(input).toHaveValue(q);
  await page.goBack();
  await expect(page).toHaveURL(`${origin}${path(q)}`);
  await expect(
    page.getByRole("link", { name: "Réponses", exact: true }),
  ).toHaveAttribute("aria-current", "page");
  expect(errors).toEqual([]);
});

test("pagination des réponses, curseur intact, retour arrière et réinitialisation", async ({
  page,
}) => {
  const q = "pagination";
  await page.goto(`${origin}${path(q)}`);
  await expect(
    page
      .getByRole("list", { name: "Résultats Réponses" })
      .getByRole("listitem"),
  ).toHaveCount(2);
  await page.getByRole("link", { name: "Résultats suivants" }).click();
  await expect(page).toHaveURL(
    `${origin}${path(q, "answers", { cursor: "answer+2/=opaque" })}`,
  );
  await expect(
    page.getByText("Réponse du lot suivant.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Résultats suivants" }),
  ).toHaveCount(0);
  await page.goBack();
  await expect(
    page
      .getByRole("list", { name: "Résultats Réponses" })
      .getByRole("listitem"),
  ).toHaveCount(2);
  await page.getByRole("link", { name: "Résultats suivants" }).click();
  await page.getByRole("link", { name: "Questions et enquêtes" }).click();
  await expect(page).toHaveURL(`${origin}${path(q, "catalog")}`);
  await page.getByRole("link", { name: "Réponses", exact: true }).click();
  await expect(page).toHaveURL(`${origin}${path(q)}`);
});

test("les deux paginations du catalogue ne mélangent pas les curseurs", async ({
  page,
}) => {
  await page.goto(`${origin}${path("catalogue", "catalog")}`);
  await page.getByRole("link", { name: "Enquêtes suivantes" }).click();
  await expect(page).toHaveURL(
    `${origin}${path("catalogue", "catalog", { cursor_forms: "forms+2/=opaque" })}`,
  );
  await expect(
    page.getByRole("link", { name: "Enquêtes suivantes" }),
  ).toHaveCount(0);
  await expect(
    page
      .getByRole("list", { name: "Résultats Questions" })
      .getByRole("listitem"),
  ).toHaveCount(3);
  await page.getByRole("link", { name: "Questions suivantes" }).click();
  await expect(page).toHaveURL(
    `${origin}${path("catalogue", "catalog", { cursor_forms: "forms+2/=opaque", cursor_questions: "questions+2/=opaque" })}`,
  );
  await expect(
    page
      .getByRole("list", { name: "Résultats Enquêtes" })
      .getByRole("listitem"),
  ).toHaveCount(1);
  await expect(
    page
      .getByRole("list", { name: "Résultats Questions" })
      .getByRole("listitem"),
  ).toHaveCount(1);
  await expect(
    page.getByRole("link", { name: "Questions suivantes" }),
  ).toHaveCount(0);
  await page.getByLabel("Mots-clés").fill("nouveau catalogue");
  await page.getByRole("button", { name: "Rechercher", exact: true }).click();
  await expect(page).toHaveURL(
    `${origin}${path("nouveau catalogue", "catalog")}`,
  );
});

test("les résultats ouvrent les pages React et l'ancre de contribution sans lien d'auteur anonyme", async ({
  page,
}) => {
  await page.goto(`${origin}${path("navigation")}`);
  await expect(page.getByRole("link", { name: "Auteur anonyme" })).toHaveCount(
    0,
  );
  await page
    .getByRole("link", { name: "Voir la contribution complète" })
    .first()
    .click();
  await expect(page).toHaveURL(
    `${origin}/forms/${formId}/contributions/9007199254742993#answer-9007199254741993`,
  );
  await expect(page.locator("#answer-9007199254741993")).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(`${origin}${path("navigation")}`);
  await page.getByRole("link", { name: "Questions et enquêtes" }).click();
  await expect(
    page.getByRole("list", { name: "Résultats Questions" }),
  ).toBeVisible();
  await page
    .getByRole("list", { name: "Résultats Questions" })
    .getByRole("link", { name: /Comment améliorer la participation/ })
    .click();
  await expect(page).toHaveURL(`${origin}${questionPath}`);
  await page.goBack();
  await page
    .getByRole("list", { name: "Résultats Enquêtes" })
    .getByRole("link", { name: "Participation citoyenne" })
    .click();
  await expect(page).toHaveURL(`${origin}/forms/${formId}`);
});

test("paramètres invalides, listes vides, erreurs et secours ont de vrais statuts HTTP", async ({
  request,
}) => {
  for (const status of [422, 500, 503, 504]) {
    const response = await request.get(`${origin}${path(String(status))}`);
    expect(response.status()).toBe(status);
    expect(response.headers()["cache-control"]).toBe("private, no-store");
    expect(response.headers()["x-robots-tag"]).toBe("noindex, nofollow");
    const html = await response.text();
    expect(html).not.toMatch(/private SQL|SECRET|private-host/);
    expect(html).toContain("Réessayer");
    expect(html).toContain('name="q"');
  }
  expect((await request.get(`${origin}${path("invalid-json")}`)).status()).toBe(
    502,
  );
  for (const query of [
    `?q=${"x".repeat(513)}`,
    "?q=a&q=b",
    "?tab=unknown",
    "?q=a&cursor=",
  ])
    expect((await request.get(`${origin}/recherche${query}`)).status()).toBe(
      422,
    );
  for (const tab of ["answers", "catalog"]) {
    const response = await request.get(`${origin}${path("absent", tab)}`);
    expect(response.status()).toBe(200);
    expect(await response.text()).toContain(
      "Aucun résultat pour cette recherche.",
    );
  }
  const unavailable = await request.get(`http://127.0.0.1:4177${path("test")}`);
  expect(unavailable.status()).toBe(503);
  expect(await unavailable.text()).toContain("Service indisponible");
  expect((await request.get("http://127.0.0.1:4177/recherche")).status()).toBe(
    200,
  );
  expect((await request.get("http://127.0.0.1:4177/")).status()).toBe(200);
});

test("réessai manuel sans boucle et résultats conservés après une erreur de pagination", async ({
  page,
  request,
}) => {
  await request.get(`${api}/search-reset`);
  await page.goto(`${origin}${path("retry")}`);
  await expect(
    page.getByRole("heading", { name: "Service indisponible" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Réessayer" }).click();
  await expect(
    page.getByRole("list", { name: "Résultats Réponses" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Réessayer" })).toHaveCount(0);
  const calls: { query: string }[] = await (
    await request.get(`${api}/search-calls`)
  ).json();
  expect(
    calls.filter((c) => new URLSearchParams(c.query).get("q") === "retry"),
  ).toHaveLength(2);
  await page.goto(`${origin}${path("pagination-error")}`);
  await page.getByRole("link", { name: "Résultats suivants" }).click();
  await expect(
    page.getByRole("heading", { name: "Service indisponible" }),
  ).toBeVisible();
  await expect(page.getByText(/Le lot précédent reste affiché/)).toBeVisible();
  await expect(
    page.getByRole("list", { name: "Résultats Réponses" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Enquêtes", exact: true }).click();
  await expect(page).toHaveURL(`${origin}/enquetes`);
});

test("chargement, attente prolongée et annulation des recherches obsolètes", async ({
  page,
}) => {
  await page.goto(`${origin}${path("initiale")}`);
  const input = page.getByLabel("Mots-clés");
  await input.fill("slow");
  await input.press("Enter");
  await expect(
    page.getByRole("list", { name: "Résultats Réponses" }),
  ).toBeVisible();
  await expect(
    page.getByRole("status").filter({ hasText: "Chargement en cours" }),
  ).toBeVisible();
  await expect(
    page.getByRole("status").filter({ hasText: "plus de temps" }),
  ).toBeVisible({ timeout: 8500 });
  await expect(page).toHaveURL(`${origin}${path("slow")}`);
  await input.fill("slow");
  await input.press("Enter");
  await expect(
    page.getByRole("status").filter({ hasText: "Chargement en cours" }),
  ).toBeVisible();
  await input.fill("rapide");
  await input.press("Enter");
  await expect(page).toHaveURL(`${origin}${path("rapide")}`);
  await page.waitForTimeout(9000);
  await expect(page).toHaveURL(`${origin}${path("rapide")}`);
  await expect(page.getByText(/Première réponse pour rapide/)).toBeVisible();
  await expect(page.getByText(/Première réponse pour slow/)).toHaveCount(0);
});

test("clavier, mobile, zoom 200 %, annonces et validation du champ", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await page.goto(`${origin}/recherche`);
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Aller au contenu principal" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("main")).toBeFocused();
  const input = page.getByLabel("Mots-clés");
  await input.focus();
  await input.fill("clavier");
  await input.press("Enter");
  await expect(
    page.getByRole("status", { name: "État des résultats" }),
  ).toContainText("Résultats affichés");
  const tab = page.getByRole("link", { name: "Questions et enquêtes" });
  await tab.focus();
  await expect(tab).toBeFocused();
  expect(
    await tab.evaluate((node) => getComputedStyle(node).outlineStyle),
  ).not.toBe("none");
  await page.keyboard.press("Enter");
  for (const tabName of ["catalog", "answers"]) {
    await page.goto(`${origin}${path("responsive", tabName)}`);
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
  await page.goto(`${origin}${path("x".repeat(513))}`);
  await expect(input).toHaveAttribute("aria-invalid", "true");
  await expect(input).toHaveAccessibleDescription(/512 caractères/);
});

test("sans JavaScript : formulaire, onglets, pagination et liens de contribution", async ({
  browser,
}) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto(`${origin}/recherche`);
  await page.getByLabel("Mots-clés").fill("sans-js");
  await page.getByRole("button", { name: "Rechercher", exact: true }).click();
  await expect(page).toHaveURL(`${origin}${path("sans-js")}`);
  await page.getByRole("link", { name: "Résultats suivants" }).click();
  await expect(
    page.getByText("Réponse du lot suivant.", { exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Questions et enquêtes" }).click();
  await expect(page).toHaveURL(`${origin}${path("sans-js", "catalog")}`);
  await page.getByRole("link", { name: "Enquêtes suivantes" }).click();
  await page.getByRole("link", { name: "Questions suivantes" }).click();
  await expect(
    page.getByRole("list", { name: "Résultats Questions" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Réponses", exact: true }).click();
  await page
    .getByRole("link", { name: "Voir la contribution complète" })
    .first()
    .click();
  await expect(page.locator("#answer-9007199254741993")).toBeVisible();
  await context.close();
});
