import { expect, test } from "@playwright/test";

const origin = "http://127.0.0.1:4175";
const path = "/questions/9007199254741022-participation";
const choice = "/questions/9007199254741021-sujets";

// Shared mock search state is isolated from the general-search specs by avoiding reset endpoints.
test("onglets au clavier, recherche limitée à la question et retour arrière", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(`${origin}${path}`);
  const answers = page.getByRole("tab", {
    name: "Réponse à la question",
    exact: true,
  });
  const search = page.getByRole("tab", {
    name: "Rechercher dans les réponses",
  });
  await expect(answers).toHaveAttribute("aria-selected", "true");
  await answers.focus();
  await page.keyboard.press("ArrowRight");
  await expect(search).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(`${origin}${path}?tab=search`);
  await expect(search).toHaveAttribute("aria-selected", "true");
  await expect(
    page.getByRole("searchbox", {
      name: "Rechercher dans les réponses",
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.getByRole("searchbox")).toHaveAccessibleDescription(
    /Recherche plein texte en français/,
  );
  await page
    .getByRole("searchbox", {
      name: "Rechercher dans les réponses",
      exact: true,
    })
    .fill("transport");
  await page.getByRole("button", { name: "Rechercher", exact: true }).click();
  await expect(page).toHaveURL(/tab=search&q=transport&cursor=/);
  await expect(
    page.getByText(/Elle ne représente pas toutes les correspondances/),
  ).toBeVisible();
  await expect(
    page
      .getByRole("list", { name: "Réponses citoyennes" })
      .locator(":scope > li"),
  ).toHaveCount(20);
  await expect(
    page.getByRole("link", { name: "Lire la contribution complète" }).first(),
  ).toHaveAttribute("href", /#answer-/);
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute(
    "href",
    `https://cahierdedoleances.fr${path}`,
  );
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute(
    "content",
    "noindex, follow",
  );
  await page
    .getByRole("link", { name: "Afficher davantage de réponses" })
    .click();
  await expect(
    page
      .getByRole("list", { name: "Réponses citoyennes" })
      .locator(":scope > li"),
  ).toHaveCount(21);
  await page
    .getByRole("searchbox", {
      name: "Rechercher dans les réponses",
      exact: true,
    })
    .fill("logement");
  await page.getByRole("button", { name: "Rechercher", exact: true }).click();
  await expect(
    page
      .getByRole("list", { name: "Réponses citoyennes" })
      .locator(":scope > li"),
  ).toHaveCount(20);
  await expect(
    page.getByText("Une réponse pour logement.", { exact: false }),
  ).toBeVisible();
  await page.screenshot({
    path: "/tmp/question-search-desktop.png",
    fullPage: true,
  });
  await answers.click();
  await expect(page).toHaveURL(`${origin}${path}`);
  await page.goBack();
  await expect(search).toHaveAttribute("aria-selected", "true");
  expect(errors).toEqual([]);
});

test("recherche GET et pagination sans JavaScript", async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto(`${origin}${path}`);
  await page.getByRole("tab", { name: "Rechercher dans les réponses" }).click();
  await page
    .getByRole("searchbox", {
      name: "Rechercher dans les réponses",
      exact: true,
    })
    .fill("rural");
  await page.getByRole("button", { name: "Rechercher", exact: true }).click();
  await expect(page).toHaveURL(/tab=search&q=rural&cursor=/);
  await expect(
    page.getByText("Une réponse pour rural.", { exact: false }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Afficher davantage de réponses" })
    .click();
  await expect(page.getByText("Réponse du lot suivant.")).toBeVisible();
  await page.getByRole("link", { name: "Revenir au début" }).click();
  await expect(
    page.getByText("Une réponse pour rural.", { exact: false }),
  ).toBeVisible();
  await context.close();
});

test("textes Autre, recherche vide, erreurs et mobile sans débordement", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await page.goto(`${origin}${choice}?tab=search`);
  await expect(
    page.getByText(/uniquement sur les précisions libres/),
  ).toBeVisible();
  await page
    .getByRole("searchbox", {
      name: "Rechercher dans les réponses",
      exact: true,
    })
    .fill("absent");
  await page.getByRole("button", { name: "Rechercher", exact: true }).click();
  await expect(
    page.getByText(/Aucun résultat pour cette recherche/).first(),
  ).toBeVisible();
  await page
    .getByRole("searchbox", {
      name: "Rechercher dans les réponses",
      exact: true,
    })
    .fill("503");
  await page.getByRole("button", { name: "Rechercher", exact: true }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(
    page.getByRole("tab", { name: "Réponse à la question", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("searchbox", {
      name: "Rechercher dans les réponses",
      exact: true,
    })
    .fill("solidarité");
  await page.getByRole("button", { name: "Rechercher", exact: true }).click();
  await expect(page.getByText("Autre proposition A")).toBeVisible();
  await page.screenshot({
    path: "/tmp/question-search-mobile.png",
    fullPage: true,
  });
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
});

test("une erreur de pagination conserve les textes et une expiration permet la relance", async ({
  page,
  request,
}) => {
  await page.goto(`${origin}${path}?tab=search&q=pagination-error`);
  const list = page.getByRole("list", { name: "Réponses citoyennes" });
  await expect(list.locator(":scope > li")).toHaveCount(20);
  await page
    .getByRole("link", { name: "Afficher davantage de réponses" })
    .click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(list.locator(":scope > li")).toHaveCount(20);
  await page.goto(`${origin}${path}?tab=search&q=expiration-question`);
  await expect(list.locator(":scope > li")).toHaveCount(20);
  await request.get(
    "http://127.0.0.1:4176/search-expire?question_id=9007199254741022",
  );
  await page
    .getByRole("link", { name: "Afficher davantage de réponses" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Cette sélection a expiré" }),
  ).toBeVisible();
  await expect(list.locator(":scope > li")).toHaveCount(20);
  await page.getByRole("button", { name: "Relancer la recherche" }).click();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(list.locator(":scope > li")).toHaveCount(20);
});

test("le panneau suit immédiatement l’onglet pendant une navigation lente", async ({
  page,
}) => {
  await page.goto(`${origin}${path}?tab=search`);
  const labels = {
    answers: "Réponse à la question",
    search: "Rechercher dans les réponses",
  };
  for (const target of ["answers", "search"] as const) {
    const previous = target === "answers" ? "search" : "answers";
    const previousPanel = page.getByRole("tabpanel", {
      name: labels[previous],
      exact: true,
    });
    const previousHeight = await previousPanel
      .locator("..")
      .evaluate((element) => element.getBoundingClientRect().height);
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const pattern = `**${path}.data*`;
    await page.route(pattern, async (route) => {
      await gate;
      await route.continue();
    });
    try {
      await page
        .getByRole("tab", { name: labels[target], exact: true })
        .click();
      await expect(
        page.getByRole("tab", { name: labels[target], exact: true }),
      ).toHaveAttribute("aria-selected", "true");
      const panel = page.getByRole("tabpanel", {
        name: labels[target],
        exact: true,
      });
      await expect(
        panel.getByRole("region", { name: "Chargement de la page" }),
      ).toBeVisible();
      await expect(
        page.getByRole("region", { name: "Chargement de la page" }),
      ).toHaveCount(1);
      await expect(previousPanel).toBeHidden();
      await expect(page.getByRole("searchbox")).toHaveCount(0);
      const height = await panel
        .locator("..")
        .evaluate((element) => element.getBoundingClientRect().height);
      expect(height).toBeGreaterThanOrEqual(previousHeight);
    } finally {
      release();
    }
    await expect(
      page.getByRole("region", { name: "Chargement de la page" }),
    ).toHaveCount(0);
    await page.unroute(pattern);
    if (target === "answers") {
      await expect(
        page.getByRole("heading", {
          name: "Réponses à la question",
          exact: true,
        }),
      ).toBeVisible();
    } else {
      await expect(page.getByRole("searchbox")).toBeVisible();
    }
  }
});
