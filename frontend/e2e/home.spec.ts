import { expect, test } from "@playwright/test";

test("home hydrates without errors or backend requests", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  await page.route("**/*", (route) => {
    const url = new URL(route.request().url());
    if (url.hostname !== "127.0.0.1")
      throw new Error(`Unexpected external request: ${url.origin}`);
    return route.continue();
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Cahier de doléances" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Cahier de doléances" }),
  ).toHaveCSS("color", "rgb(43, 42, 38)");
  await expect(page).toHaveTitle(
    "Cahier de doléances — Les paroles citoyennes",
  );
  await expect(
    page.getByRole("link", { name: "Explorer les enquêtes" }),
  ).toHaveAttribute("href", "/enquetes");
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Aller au contenu principal" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("main")).toBeFocused();
  expect(errors).toEqual([]);
});

test("essential content is accessible without JavaScript", async ({
  browser,
}) => {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 320, height: 900 },
  });
  const page = await context.newPage();
  await page.goto("http://127.0.0.1:4173/");
  await expect(
    page.getByRole("heading", { name: "Cahier de doléances" }),
  ).toBeVisible();
  await expect(
    page.getByText(/Des paroles citoyennes à découvrir/),
  ).toBeVisible();
  await context.close();
});

for (const width of [320, 375, 768, 1280]) {
  for (const textSize of [100, 200]) {
    test(`home fits at ${width}px with text at ${textSize}%`, async ({
      page,
    }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/");
      await page.evaluate((size) => {
        document.documentElement.style.fontSize = `${size}%`;
      }, textSize);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBe(true);
      const brand = page.getByRole("link", {
        name: "Accueil — Cahier de doléances",
      });
      await expect(brand.locator("img")).toHaveAttribute("src", "/favicon.svg");
      await expect(brand).toHaveAttribute("href", "/");
      for (const name of [
        "Enquêtes",
        "Recherche",
        "Explorer les enquêtes",
        "Rechercher dans les contributions",
      ]) {
        const box = await page
          .getByRole("link", { name, exact: true })
          .boundingBox();
        expect(box?.height).toBeGreaterThanOrEqual(44);
      }
      const title = await page.locator("h1").boundingBox();
      const spiral = await page.locator("section img").boundingBox();
      const introduction = await page
        .getByText(/Des paroles citoyennes à découvrir/)
        .boundingBox();
      const explore = await page
        .getByRole("link", { name: "Explorer les enquêtes" })
        .boundingBox();
      const search = await page
        .getByRole("link", { name: "Rechercher dans les contributions" })
        .boundingBox();
      expect(title).not.toBeNull();
      expect(spiral).not.toBeNull();
      expect(introduction).not.toBeNull();
      expect(explore).not.toBeNull();
      expect(search).not.toBeNull();
      if (!title || !spiral || !introduction || !explore || !search) return;
      expect(spiral.width).toBeCloseTo(spiral.height, 0);
      if (width < 768 && textSize === 100) {
        expect(
          await page
            .locator("header")
            .evaluate((el) => el.getBoundingClientRect().height),
        ).toBeLessThan(130);
      }
      if (width < 768) {
        expect(spiral.y).toBeGreaterThanOrEqual(title.y + title.height);
        expect(introduction.y).toBeGreaterThanOrEqual(spiral.y + spiral.height);
        expect(explore.y).toBeGreaterThanOrEqual(
          introduction.y + introduction.height,
        );
        expect(search.y).toBeGreaterThanOrEqual(explore.y + explore.height);
        await expect(
          page.getByText("Consultations publiques", { exact: true }),
        ).toBeHidden();
      }
      if (width === 1280 && textSize === 100) {
        expect(spiral.x).toBeGreaterThanOrEqual(title.x + title.width);
        expect(spiral.width).toBeGreaterThan(400);
        expect(
          await page
            .locator("header")
            .evaluate((el) => el.getBoundingClientRect().height),
        ).toBeLessThan(100);
      }
    });
  }
}
