// Invoked exclusively by scripts/smoke_search_browser.py, never by the application.

import { createInterface } from "node:readline";
import { chromium, expect } from "@playwright/test";

const lines = createInterface({ input: process.stdin });
const replies = lines[Symbol.asyncIterator]();
async function control(action) {
  process.stdout.write(`${JSON.stringify({ action })}\n`);
  const reply = JSON.parse((await replies.next()).value);
  if (!reply.ok) throw new Error("Local smoke control failed");
  return reply;
}
const browser = await chromium.launch({ headless: true });
const results = [];
try {
  for (const javaScriptEnabled of [true, false]) {
    const context = await browser.newContext({ javaScriptEnabled });
    // Browser requests are constrained to this disposable local harness.
    await context.route("**/*", (route) => {
      const url = new URL(route.request().url());
      return ["127.0.0.1", "localhost"].includes(url.hostname)
        ? route.continue()
        : route.abort();
    });
    const page = await context.newPage();
    const before = await control("count");
    await page.goto("http://127.0.0.1:4185/recherche");
    await page
      .getByLabel("Votre question ou votre sujet")
      .fill("Comment améliorer les transports publics ?");
    const start = performance.now();
    await page.getByRole("button", { name: "Rechercher", exact: true }).click();
    await expect(
      page.getByRole("list", { name: "Réponses citoyennes", exact: true }),
    ).toBeVisible({ timeout: 25000 });
    const searchSeconds = (performance.now() - start) / 1000;
    const firstUrl = page.url();
    if (!new URL(firstUrl).searchParams.get("cursor"))
      throw new Error("Missing first cursor");
    const href = await page
      .getByRole("link", { name: "Lire la contribution complète" })
      .first()
      .getAttribute("href");
    const answerId = new URL(href, "http://127.0.0.1").hash.slice(1);
    const cards = await page
      .getByRole("list", { name: "Réponses citoyennes", exact: true })
      .getByRole("listitem")
      .count();
    if (javaScriptEnabled)
      await page.screenshot({
        path: "/tmp/search-005-desktop.png",
        fullPage: false,
      });
    await page
      .getByRole("link", { name: "Lire la contribution complète" })
      .first()
      .click();
    const target = page.locator(`#${answerId}`);
    await expect(target).toBeVisible();
    await expect
      .poll(async () => (await target.boundingBox())?.y)
      .toBeLessThan(250);
    await page.goBack();
    await expect(page).toHaveURL(firstUrl);
    const nextStart = performance.now();
    await page
      .getByRole("link", { name: "Page suivante", exact: true })
      .click();
    await expect(
      page.getByRole("link", { name: "Page précédente", exact: true }),
    ).toBeVisible();
    const paginationSeconds = (performance.now() - nextStart) / 1000;
    await page.reload();
    await page
      .getByRole("link", { name: "Première page", exact: true })
      .click();
    await expect(page).toHaveURL(firstUrl);
    const after = await control("count");
    if (after.count - before.count !== 1)
      throw new Error("Pagination recalculated H1");
    await control("expire");
    const expired = await page.reload();
    if (expired.status() !== 410)
      throw new Error(`Expiration HTTP ${expired.status()}`);
    await expect(
      page.getByRole("heading", { name: "Cette sélection a expiré" }),
    ).toBeVisible();
    const expiredCount = await control("count");
    if (expiredCount.count !== after.count)
      throw new Error("Silent recalculation");
    await page
      .getByRole("button", { name: "Relancer la recherche", exact: true })
      .click();
    await expect(
      page.getByRole("list", { name: "Réponses citoyennes", exact: true }),
    ).toBeVisible({ timeout: 25000 });
    await control("empty_on");
    const empty = await page.goto(
      "http://127.0.0.1:4185/recherche?q=Verification%20du%20rendu%20vide",
    );
    if (empty.status() !== 200) throw new Error("Empty response not HTTP 200");
    await expect(
      page.getByText(/Essayez de préciser votre sujet/),
    ).toBeVisible();
    await control("empty_off");
    results.push({
      javaScriptEnabled,
      cards,
      searchSeconds,
      paginationSeconds,
      anchor: "verified",
      paginationH1Calls: 0,
      expiryStatus: expired.status(),
      emptyState: "injected_empty_ranking",
    });
    await context.close();
  }
  process.stdout.write(`${JSON.stringify({ results })}\n`);
} finally {
  await browser.close();
  lines.close();
}
