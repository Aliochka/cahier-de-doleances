import { expect, test } from "@playwright/test";

const origin = "http://127.0.0.1:4175";
const question = "/questions/9007199254741022-participation";
const author = "/authors/9007199254743993";

test("question : ajoute, garde la position et restaure les deux lots après une contribution", async ({
  page,
}) => {
  await page.goto(`${origin}${question}`);
  const list = page.getByRole("list", {
    name: "Réponses à la question",
    exact: true,
  });
  await expect(list.locator(":scope > li")).toHaveCount(1);
  await page
    .getByRole("link", { name: "Afficher davantage de réponses", exact: true })
    .click();
  await expect(list.locator(":scope > li")).toHaveCount(2);
  await expect(list.locator(":scope > li").last()).toBeFocused();
  await expect(page).toHaveURL(/cursor=/);
  const link = list
    .locator(":scope > li")
    .last()
    .getByRole("link", { name: "Voir la contribution complète" });
  await link.scrollIntoViewIfNeeded();
  const y = await page.evaluate(() => scrollY);
  await link.click();
  await expect(
    page.getByRole("list", { name: "Réponses de la contribution" }),
  ).toBeVisible();
  await page.goBack();
  await expect(list.locator(":scope > li")).toHaveCount(2);
  await expect
    .poll(async () => Math.abs((await page.evaluate(() => scrollY)) - y))
    .toBeLessThan(5);
  await page.reload();
  await expect(list.locator(":scope > li")).toHaveCount(1);
  await expect(page.getByText("Réponse du lot suivant.")).toBeVisible();
});
test("auteur : les lots se regroupent sans répéter un formulaire", async ({
  page,
}) => {
  await page.goto(`${origin}${author}`);
  await page
    .getByRole("link", {
      name: "Afficher davantage de contributions",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("link", { name: /Consulter la contribution/ }),
  ).toHaveCount(4);
  await expect(
    page.getByRole("heading", { name: "Participation citoyenne", exact: true }),
  ).toHaveCount(1);
});
test("sans JavaScript : le même bouton ouvre uniquement le lot suivant", async ({
  browser,
}) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto(`${origin}${question}`);
  await page
    .getByRole("link", { name: "Afficher davantage de réponses", exact: true })
    .click();
  await expect(page).toHaveURL(/cursor=/);
  await expect(
    page
      .getByRole("list", { name: "Réponses à la question", exact: true })
      .locator(":scope > li"),
  ).toHaveCount(1);
  await expect(page.getByText("Réponse du lot suivant.")).toBeVisible();
  await context.close();
});
