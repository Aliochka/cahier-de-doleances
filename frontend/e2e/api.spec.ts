import { expect, test } from "@playwright/test";

const fixture = "http://127.0.0.1:4175/_test/api";

test("le serveur renvoie du HTML exploitable et les vrais statuts d'erreur", async ({
  request,
}) => {
  const success = await request.get(fixture, {
    headers: {
      Cookie: "session_token=synthetic",
      "X-Forwarded-Host": "untrusted.invalid",
    },
  });
  expect(success.status()).toBe(200);
  expect(await success.text()).toContain("Formulaire synthétique");
  expect(await success.text()).toContain("9007199254740993");
  for (const [id, status, heading] of [
    [404, 404, "Page introuvable"],
    [500, 500, "Une erreur est survenue"],
    [503, 503, "Service indisponible"],
    [504, 504, "Une erreur est survenue"],
  ] as const) {
    const response = await request.get(`${fixture}?id=${id}`);
    expect(response.status()).toBe(status);
    const html = await response.text();
    expect(html).toContain(heading);
    expect(html).not.toContain("private SQL");
    expect(html).not.toContain("127.0.0.1:4176");
    expect(response.headers()["cache-control"]).toBe("private, no-store");
    expect(response.headers()["x-robots-tag"]).toContain("noindex");
  }
  expect((await request.get("/_test/api")).status()).toBe(404);
});

test("une panne réseau donne 503 et laisse l'accueil pré-rendu accessible", async ({
  request,
}) => {
  // A separate fixture server configured to a closed loopback port, never Wallace.
  const unavailable = await request.get("http://127.0.0.1:4177/_test/api");
  expect(unavailable.status()).toBe(503);
  expect(await unavailable.text()).toContain("Service indisponible");
  const home = await request.get("http://127.0.0.1:4177/");
  expect(home.status()).toBe(200);
  expect(await home.text()).toContain("Cahier de doléances");
});

test("le réessai est manuel, récupère la page et permet la navigation suivante", async ({
  page,
  request,
}) => {
  await request.get("http://127.0.0.1:4176/reset");
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(`${fixture}?id=7`);
  await expect(
    page.getByRole("heading", { name: "Service indisponible" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Réessayer" }).click();
  await expect(page.getByText("Formulaire synthétique")).toBeVisible();
  await page.getByRole("link", { name: "Accueil", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Cahier de doléances", exact: true }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("attente prolongée puis navigation obsolète ne remplace pas la lecture courante", async ({
  page,
}) => {
  test.setTimeout(30_000);
  await page.goto(fixture);
  await page.getByRole("link", { name: "Lecture lente" }).click();
  await expect(page.getByRole("status")).toContainText("Chargement en cours");
  await expect(page.getByText("Formulaire synthétique")).toBeVisible();
  await expect(page.getByRole("status")).toContainText("plus de temps", {
    timeout: 8500,
  });
  await expect(page.getByTestId("id")).toHaveText("8");
  await page.getByRole("link", { name: "Lecture normale" }).click();
  await expect(page.getByTestId("id")).toHaveText("9007199254740993");
  await page.getByRole("link", { name: "Lecture lente" }).click();
  await expect(page.getByRole("status")).toBeVisible();
  await page.getByRole("link", { name: "Lecture normale" }).click();
  await expect(page.getByRole("status")).toBeHidden();
  await page.waitForTimeout(9000);
  await expect(page.getByTestId("id")).toHaveText("9007199254740993");
});

test("le navigateur utilise le chemin relatif et omet les cookies publics", async ({
  page,
}) => {
  await page.goto("http://127.0.0.1:4174/dev/components", {
    waitUntil: "networkidle",
  });
  await page.context().addCookies([
    {
      name: "session_token",
      value: "synthetic",
      url: "http://127.0.0.1:4174",
    },
  ]);
  let requested = "";
  let cookie: string | undefined;
  await page.route("**/api/v1/forms/*", async (route) => {
    requested = route.request().url();
    cookie = route.request().headers().cookie;
    await route.fulfill({
      json: {
        id: "9007199254740993",
        name: "Exemple",
        url: "/forms/9007199254740993",
        questions_count: 0,
        questions: [],
      },
    });
  });
  const result = await page.evaluate(
    `import('/app/lib/api.ts').then(({createPublicApi}) => createPublicApi().getForm('9007199254740993', {query: new URLSearchParams({q: 'école'})}))`,
  );
  expect(requested).toBe(
    "http://127.0.0.1:4174/api/v1/forms/9007199254740993?q=%C3%A9cole",
  );
  expect(cookie).toBeUndefined();
  expect(result).toMatchObject({ ok: true, data: { id: "9007199254740993" } });
});
