import { expect, type Locator, type Page } from "@playwright/test";

export async function checkCitizenReading(page: Page, paragraph: Locator) {
  for (const heading of await page.locator("h1, h2, h3").all()) {
    await expect(heading).toHaveCSS("font-family", /Special Elite/);
  }
  const documentLinks = page.locator("main a");
  for (const link of await documentLinks.all()) {
    await expect(link).toHaveCSS("font-family", /Special Elite/);
  }
  for (const control of await page
    .locator("main input, main button, main select")
    .all()) {
    await expect(control).toHaveCSS("font-family", /system-ui/);
  }
  const original = await paragraph.textContent();
  await expect(paragraph).toHaveCSS("font-family", /Literata/);
  await expect(paragraph).toHaveCSS("color", "rgb(43, 42, 38)");
  await expect(paragraph).toHaveCSS("white-space", "pre-wrap");
  for (const width of [320, 375, 768, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    for (const scale of [1, 2]) {
      await page.evaluate((scale) => {
        document.documentElement.style.fontSize = `${100 * scale}%`;
      }, scale);
      await expect(paragraph).toHaveCSS("font-size", `${18 * scale}px`);
      await expect(paragraph).toHaveCSS("line-height", `${32.4 * scale}px`);
      expect((await paragraph.boundingBox())?.width).toBeLessThanOrEqual(
        672 * scale,
      );
      // Stress wrapping locally in the browser, without changing fixture/API data.
      await paragraph.evaluate((el) => {
        el.textContent += `\n\nhttps://exemple.fr/${"mottrèslong".repeat(100)}`;
      });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBe(true);
      await paragraph.evaluate((el, text) => {
        el.textContent = text;
      }, original);
      expect(await paragraph.textContent()).toBe(original);
    }
  }
  await page.setViewportSize({ width: 320, height: 900 });
  await page.evaluate(() => {
    document.documentElement.style.fontSize = "100%";
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
