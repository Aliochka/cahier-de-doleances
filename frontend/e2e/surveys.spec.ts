import { expect, test } from "@playwright/test";

const origin = "http://127.0.0.1:4175";
const formPath = "/forms/9007199254740995";

test("les deux pages fournissent leur contenu et leurs métadonnées dans le HTML SSR", async ({
  request,
}) => {
  for (const [path, title] of [
    ["/enquetes", "Enquêtes du Grand Débat"],
    [formPath, "Participation citoyenne"],
  ]) {
    const response = await request.get(`${origin}${path}`, {
      headers: {
        Cookie: "session_token=synthetic",
        "X-Forwarded-Host": "untrusted.invalid",
      },
    });
    expect(response.status()).toBe(200);
    const html = await response.text();
    expect(html).toContain(`<title>${title}`);
    expect(html).toContain('name="description"');
    expect(html).toContain(
      `rel="canonical" href="https://cahierdedoleances.fr${path}"`,
    );
    expect(html).not.toContain('content="noindex');
    expect(html).not.toContain("127.0.0.1:4176");
    expect(response.headers()["cache-control"]).toBe("private, no-store");
    expect(response.headers()["set-cookie"]).toBeUndefined();
    if (path === formPath) {
      expect(html).toContain("Comment améliorer la participation citoyenne");
      expect(html).toContain("Quel mode de consultation privilégier");
      expect(html).toContain("Quels sujets souhaitez-vous aborder");
    }
  }
});

test("les pages renvoient les vrais statuts 404, 500, 503 et 504 sans divulgation", async ({
  request,
}) => {
  for (const [id, title] of [
    [404, "Page introuvable"],
    [500, "Une erreur est survenue"],
    [503, "Service indisponible"],
    [504, "Une erreur est survenue"],
  ] as const) {
    const response = await request.get(`${origin}/forms/${id}`);
    expect(response.status()).toBe(id);
    const html = await response.text();
    expect(html).toContain(title);
    expect(html).toContain("Retour aux enquêtes");
    expect(html).toContain('content="noindex, nofollow"');
    expect(html).not.toContain("private SQL");
    expect(response.headers()["x-robots-tag"]).toContain("noindex");
    expect(response.headers()["cache-control"]).toBe("private, no-store");
  }
  for (const path of ["/enquetes", formPath]) {
    const response = await request.get(`http://127.0.0.1:4177${path}`);
    expect(response.status()).toBe(503);
    expect(await response.text()).toContain("Service indisponible");
  }
  expect((await request.get("http://127.0.0.1:4177/")).status()).toBe(200);
});

test("une URL contrib reste explicite et non indexable, sans substitution ni dépendance API", async ({
  page,
  request,
}) => {
  const response = await request.get(
    `http://127.0.0.1:4177${formPath}?contrib=2`,
  );
  expect(response.status()).toBe(404);
  expect(response.headers()["x-robots-tag"]).toContain("noindex");
  const html = await response.text();
  expect(html).toContain("introuvable");
  expect(html).not.toContain("Comment améliorer la participation citoyenne");
  expect(html).not.toContain('rel="canonical"');
  await page.goto(`${origin}${formPath}?contrib=2`);
  await expect(
    page.getByRole("heading", { name: "Page introuvable" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Retour aux enquêtes" }).click();
  await page.getByRole("link", { name: "Participation citoyenne" }).click();
  await expect(page).toHaveURL(`${origin}${formPath}`);
  await expect(
    page.getByRole("list", { name: "Questions du formulaire" }),
  ).toBeVisible();
});

test("navigation interne, retour arrière, clavier et hydratation", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  await page.goto(`${origin}/enquetes`);
  await expect(
    page.getByRole("navigation").getByRole("link", { name: "Enquêtes" }),
  ).toHaveAttribute("aria-current", "page");
  const cards = page.getByRole("list", { name: "Formulaires du Grand Débat" });
  await expect(cards.getByRole("heading")).toHaveText([
    "Participation citoyenne",
    "Formulaire synthétique",
  ]);
  await page.evaluate(() => {
    Object.defineProperty(window, "__navigationMarker", { value: "retained" });
  });
  const link = page.getByRole("link", { name: "Participation citoyenne" });
  await link.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(`${origin}${formPath}`);
  expect(await page.evaluate("window.__navigationMarker")).toBe("retained");
  const questions = page.getByRole("list", { name: "Questions du formulaire" });
  await expect(questions.getByRole("heading")).toHaveText([
    "Comment améliorer la participation citoyenne et permettre à chacun de contribuer aux décisions publiques, y compris dans les territoires les plus éloignés ?",
    "Quel mode de consultation privilégier ?",
    "Quels sujets souhaitez-vous aborder ?",
  ]);
  await expect(questions.locator("h2 a")).toHaveCount(3);
  await page.goBack();
  await expect(
    page.getByRole("heading", { name: "Enquêtes", exact: true }),
  ).toBeVisible();
  await link.click();
  await page.getByRole("link", { name: "← Retour aux enquêtes" }).click();
  await expect(page).toHaveURL(`${origin}/enquetes`);
  expect(errors).toEqual([]);
});

test("lecture mobile, zoom 200 %, questionnaire vide et lien d'évitement", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await page.goto(`${origin}${formPath}`);
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Aller au contenu principal" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("main")).toBeFocused();
  for (const path of [formPath, "/enquetes", "/forms/9007199254740993"]) {
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
  await expect(
    page.getByText("Ce formulaire ne contient aucune question."),
  ).toBeVisible();
});

test("les nouvelles routes réutilisent le chargement et l'attente prolongée", async ({
  page,
}) => {
  await page.goto(`${origin}/enquetes`);
  // Delay React Router's data response locally; no request reaches Wallace.
  await page.route("**/forms/9007199254740995.data*", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 8500));
    await route.continue();
  });
  await page.getByRole("link", { name: "Participation citoyenne" }).click();
  await expect(page.getByRole("status")).toContainText("Chargement en cours");
  await expect(
    page.getByRole("heading", { name: "Enquêtes", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("status")).toContainText("plus de temps", {
    timeout: 8500,
  });
  await expect(
    page.getByRole("heading", { name: "Participation citoyenne", exact: true }),
  ).toBeVisible();
});

test("le réessai du formulaire récupère la route sans boucle ni maintenance globale", async ({
  page,
  request,
}) => {
  await request.get("http://127.0.0.1:4176/reset-form");
  await page.goto(`${origin}/forms/9`);
  await expect(
    page.getByRole("heading", { name: "Service indisponible" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Réessayer" }).click();
  await expect(
    page.getByRole("heading", { name: "Formulaire synthétique" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Réessayer" })).toHaveCount(0);
  await page.getByRole("link", { name: "← Retour aux enquêtes" }).click();
  await expect(
    page.getByRole("heading", { name: "Enquêtes", exact: true }),
  ).toBeVisible();
});

test("le contenu essentiel des pages métier est lisible sans JavaScript", async ({
  browser,
}) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto(`${origin}/enquetes`);
  await page.getByRole("link", { name: "Participation citoyenne" }).click();
  await expect(
    page.getByRole("heading", { name: "Participation citoyenne", exact: true }),
  ).toBeVisible();
  await expect(
    page
      .getByRole("list", { name: "Questions du formulaire" })
      .locator(":scope > li"),
  ).toHaveCount(3);
  await context.close();
});
