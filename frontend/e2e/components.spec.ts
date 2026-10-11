import { expect, test } from "@playwright/test";

const demo = "http://127.0.0.1:4174/dev/components";

test("la démonstration est réellement introuvable en production", async ({
  request,
}) => {
  const response = await request.get("/dev/components");
  expect(response.status()).toBe(404);
  expect(await response.text()).not.toContain("Atelier des composants");
});

test("le lien d'évitement donne le focus au contenu", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Aller au contenu principal" });
  await expect(skip).toBeFocused();
  await expect(skip).toBeInViewport();
  await expect(skip).toHaveCSS("outline-style", "solid");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("main")).toBeFocused();
});

test("SSR, hydratation, onglets et dialogue fonctionnent au clavier", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  const response = await request.get(demo);
  expect(response.status()).toBe(200);
  const html = await response.text();
  expect(html).toContain("Le premier panneau est rendu côté serveur.");
  expect(html).toContain('role="tab"');
  await page.goto(demo, { waitUntil: "networkidle" });
  const first = page.getByRole("tab", { name: "Présentation", exact: true });
  const second = page.getByRole("tab", { name: "Exemples", exact: true });
  await first.focus();
  await page.keyboard.press("ArrowRight");
  await expect(second).toBeFocused();
  await expect(second).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("Home");
  await expect(first).toHaveAttribute("aria-selected", "true");
  const trigger = page.getByRole("button", { name: "Afficher un dialogue" });
  await trigger.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: "Un dialogue accessible" });
  await expect(dialog).toBeVisible();
  await expect(dialog).toHaveAccessibleDescription(
    "Le focus reste dans cette fenêtre jusqu’à sa fermeture.",
  );
  for (let index = 0; index < 6; index++) {
    await page.keyboard.press("Tab");
    expect(
      await dialog.evaluate((element) =>
        element.contains(document.activeElement),
      ),
    ).toBe(true);
  }
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(trigger).toBeFocused();
  await trigger.click();
  await page.getByRole("button", { name: "Fermer", exact: true }).click();
  await expect(trigger).toBeFocused();
  expect(errors).toEqual([]);
});

for (const width of [320, 768, 1280]) {
  test(`la démonstration et le dialogue ne débordent pas à ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 720 });
    await page.goto(demo, { waitUntil: "networkidle" });
    const noOverflow = () =>
      page.evaluate(
        () =>
          document.documentElement.scrollWidth <=
          document.documentElement.clientWidth,
      );
    expect(await noOverflow()).toBe(true);
    await page.getByRole("button", { name: "Afficher un dialogue" }).click();
    await expect(page.getByRole("dialog")).toBeVisible();
    expect(await noOverflow()).toBe(true);
    await page.keyboard.press("Escape");
    await page.emulateMedia({ reducedMotion: "reduce" });
    await expect(page.locator("[data-skeleton]").first()).toHaveCSS(
      "animation-name",
      "none",
    );
  });
}
