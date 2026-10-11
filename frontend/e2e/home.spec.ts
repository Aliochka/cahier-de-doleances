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
  ).toHaveCSS("color", "rgb(32, 58, 143)");
  await expect(page).toHaveTitle(
    "Cahier de doléances — Les voix du Grand Débat",
  );
  const trigger = page.getByRole("button", { name: "À propos du projet" });
  await trigger.click();
  await expect(trigger).toHaveAttribute("aria-expanded", "false");
  await trigger.click();
  await expect(trigger).toHaveAttribute("aria-expanded", "true");
  await trigger.press("Enter");
  await expect(trigger).toHaveAttribute("aria-expanded", "false");
  await trigger.press("Space");
  await expect(trigger).toHaveAttribute("aria-expanded", "true");
  expect(errors).toEqual([]);
});

test("essential content is accessible without JavaScript", async ({
  browser,
}) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto("http://127.0.0.1:4173/");
  await expect(
    page.getByRole("heading", { name: "Cahier de doléances" }),
  ).toBeVisible();
  await expect(
    page.getByText(/contributions citoyennes du Grand Débat National et/),
  ).toBeVisible();
  await context.close();
});
