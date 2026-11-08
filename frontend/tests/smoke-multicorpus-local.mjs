import { chromium } from "@playwright/test";

const origin = new URL(
  process.env.MULTICORPUS_APP_URL || "http://127.0.0.1:3000",
);
if (
  origin.protocol !== "http:" ||
  !["127.0.0.1", "localhost"].includes(origin.hostname)
)
  throw Error("Local application only");
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.route("**/*", (route) =>
    new URL(route.request().url()).origin === origin.origin
      ? route.continue()
      : route.abort(),
  );
  await page.goto(`${origin.origin}/parcourir`);
  await page.getByRole("heading", { name: "Parcourir les corpus" }).waitFor();
  if (
    !(
      await page
        .getByRole("navigation", { name: "Navigation principale" })
        .getByRole("link", { name: "Parcourir" })
        .evaluate((n) => getComputedStyle(n).fontFamily)
    ).includes("Special Elite")
  )
    throw Error("Navigation design system missing");
  await page
    .getByRole("link", { name: "Cahiers de doléances — 1789", exact: true })
    .click();
  await page
    .getByRole("heading", { level: 1, name: "Cahiers de doléances — 1789" })
    .waitFor();
  const catalogue = page.getByRole("list", { name: "Catalogue des cahiers" });
  if ((await catalogue.locator("li").count()) !== 20)
    throw Error("Catalogue page size");
  await page.screenshot({ path: "/tmp/phase4-catalogue.png", fullPage: false });
  await catalogue.locator("h2 a").first().click();
  const reading = page.getByRole("region", {
    name: "Texte intégral du cahier",
  });
  await reading.waitFor();
  if (!(await reading.textContent()).trim()) throw Error("Full text empty");
  if (
    !(await reading.evaluate((n) => getComputedStyle(n).fontFamily)).includes(
      "Literata",
    )
  )
    throw Error("Reading font missing");
  if (
    !(
      await page
        .getByRole("heading", { level: 1 })
        .evaluate((n) => getComputedStyle(n).fontFamily)
    ).includes("Special Elite")
  )
    throw Error("Title font missing");
  await page.setViewportSize({ width: 375, height: 900 });
  if (
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth + 2,
    )
  )
    throw Error("Reader mobile overflow");
  await page.screenshot({
    path: "/tmp/phase4-reader-mobile.png",
    fullPage: false,
  });
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.getByRole("link", { name: "Cahier suivant →" }).first().click();
  await page
    .getByRole("link", { name: "← Cahier précédent" })
    .first()
    .waitFor();
  await page.goto(`${origin.origin}/recherche?q=Gabelle&corpus=1789`);
  await page.locator("#search-results-title").waitFor();
  await page.waitForFunction(() =>
    new URL(location.href).searchParams.has("cursor"),
  );
  const firstUrl = page.url();
  const ids = await page
    .locator("[data-progressive-id]")
    .evaluateAll((ns) => ns.map((n) => n.dataset.progressiveId));
  if (ids.length !== 20 || ids.some((id) => !id.startsWith("1789:")))
    throw Error("Historical selection");
  await page
    .getByRole("link", { name: "Lire le cahier intégral à cet emplacement" })
    .first()
    .click();
  await page.locator('mark[id^="passage-"]').waitFor();
  if (!(await page.locator("mark").allTextContents()).join("").trim())
    throw Error("Empty selected passage");
  await page.goBack();
  await page.locator("#search-results-title").waitFor();
  if (page.url() !== firstUrl) throw Error("Search back URL changed");
  await page
    .getByRole("link", { name: "Afficher davantage de résultats" })
    .click();
  await page.waitForFunction(
    () => document.querySelectorAll("[data-progressive-id]").length === 40,
  );
  const allIds = await page
    .locator("[data-progressive-id]")
    .evaluateAll((ns) => ns.map((n) => n.dataset.progressiveId));
  if (new Set(allIds).size !== 40)
    throw Error("Duplicate documents across pages");
  await page.reload();
  await page.waitForLoadState("networkidle");
  await page.locator("#search-results-title").waitFor();
  if ((await page.locator("#search-corpus").inputValue()) !== "1789")
    throw Error("Corpus lost on reload");
  await page.selectOption("#search-corpus", "2019");
  await page.waitForFunction(
    () =>
      new URL(location.href).searchParams.get("corpus") === "2019" &&
      !!new URL(location.href).searchParams.get("cursor"),
  );
  await page.locator("#search-results-title").waitFor();
  if (
    (
      await page
        .locator("[data-progressive-id]")
        .evaluateAll((ns) => ns.map((n) => n.dataset.progressiveId))
    ).some((id) => id.startsWith("1789:"))
  )
    throw Error("Wrong corpus after filter");
  if (new URL(page.url()).searchParams.get("q") !== "Gabelle")
    throw Error("Query lost");
  await page.goBack();
  await page.waitForFunction(
    () => document.querySelector("#search-corpus").value === "1789",
  );
  await page.goForward();
  await page.waitForFunction(
    () => document.querySelector("#search-corpus").value === "2019",
  );
  await page.selectOption("#search-corpus", "tous");
  await page.waitForFunction(
    () =>
      new URL(location.href).searchParams.get("corpus") === "tous" &&
      !!new URL(location.href).searchParams.get("cursor"),
  );
  await page.locator("#search-results-title").waitFor();
  await page.screenshot({ path: "/tmp/phase4-search.png", fullPage: false });
  await page.locator("#search-corpus").focus();
  if (
    !(await page
      .locator("#search-corpus")
      .evaluate((n) => n === document.activeElement))
  )
    throw Error("Keyboard focus");
  await page.keyboard.press("Tab");
  if (
    !(await page
      .getByRole("button", { name: "Rechercher", exact: true })
      .evaluate((n) => n === document.activeElement))
  )
    throw Error("Keyboard tab order");

  for (const width of [375, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    if (
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth + 2,
      )
    )
      throw Error("Horizontal overflow");
    if (width === 375)
      await page.screenshot({
        path: "/tmp/phase4-mobile.png",
        fullPage: false,
      });
  }

  await page.selectOption("#search-corpus", "2019");
  await page.waitForFunction(
    () =>
      new URL(location.href).searchParams.get("corpus") === "2019" &&
      !!new URL(location.href).searchParams.get("cursor"),
  );
  await page.locator("#search-results-title").waitFor();
  await page
    .getByRole("link", { name: "Lire la contribution complète", exact: true })
    .first()
    .click();
  await page.getByRole("heading", { level: 1, name: /Contribution/ }).waitFor();
  const answerAnchor = new URL(page.url()).hash.slice(1);
  if (
    !answerAnchor ||
    !(await page.evaluate(
      (id) => document.getElementById(id) !== null,
      answerAnchor,
    ))
  )
    throw Error("Answer deep link");
  await page.goto(`${origin.origin}/enquetes`);
  await page.getByRole("heading", { level: 1, name: "Enquêtes" }).waitFor();
  await page.locator("h3 a").first().click();
  await page.waitForURL(/\/forms\/\d+/);
  await page.getByRole("heading", { level: 1 }).waitFor();
  if (errors.length) throw Error(errors.join("\n"));
  console.log(
    JSON.stringify({
      gdn_navigation: true,
      catalogue: true,
      reader: true,
      unicode_anchor: true,
      previous_next: true,
      corpus_url: true,
      reload: true,
      back_forward: true,
      pagination_without_duplicates: true,
      keyboard: true,
      design_system: true,
      responsive: true,
      page_errors: errors,
    }),
  );
} finally {
  await browser.close();
}
