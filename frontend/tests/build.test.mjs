import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import test from "node:test";
import { createRequestHandler } from "react-router";
import * as build from "../build/server/index.js";

test("prerender includes essential content, metadata and Panda styles", async () => {
  const html = await readFile("build/client/index.html", "utf8");
  assert.match(html, /<html lang="fr"/);
  assert.match(html, /<h1[^>]*>Cahier de doléances<\/h1>/);
  assert.match(html, /contributions citoyennes du Grand Débat National/);
  assert.match(
    html,
    /<title>Cahier de doléances — Les voix du Grand Débat<\/title>/,
  );
  assert.match(html, /<meta name="description"/);
  assert.match(html, /rel="stylesheet"[^>]*\/assets\//);
  const assets = await readdir("build/client/assets");
  const css = (
    await Promise.all(
      assets
        .filter((file) => file.endsWith(".css"))
        .map((file) => readFile(`build/client/assets/${file}`, "utf8")),
    )
  ).join("\n");
  assert.match(css, /#203a8f/i);
  assert.match(css, /#f2f1ea/i);
  assert.match(css, /font-family/);
});

test("built SSR returns a complete document and safe 404 without network access", async () => {
  const handle = createRequestHandler(build, "production");
  const response = await handle(new Request("http://localhost/"));
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type"), /text\/html/);
  assert.match(await response.text(), /<h1[^>]*>Cahier de doléances<\/h1>/);
  const missing = await handle(new Request("http://localhost/missing"));
  assert.equal(missing.status, 404);
  const html = await missing.text();
  assert.match(html, /Page introuvable/);
  assert.match(html, /noindex, nofollow/);
  assert.doesNotMatch(html, /stack trace|node_modules/);
});

test("Netlify produces a Node function that prefers prerendered files", async () => {
  const handler = await import(
    "../.netlify/v1/functions/react-router-server.mjs"
  );
  assert.equal(typeof handler.default, "function");
  assert.equal(handler.config.preferStatic, true);
  assert.match(handler.config.generator, /@netlify\/vite-plugin-react-router/);
});

test("development components route is absent from the production manifest and returns 404", async () => {
  assert.equal(
    Object.values(build.routes).some(
      (route) => route.path === "dev/components",
    ),
    false,
  );
  const response = await createRequestHandler(
    build,
    "production",
  )(new Request("http://localhost/dev/components"));
  assert.equal(response.status, 404);
  assert.doesNotMatch(await response.text(), /Atelier des composants/);
});

test("normal build excludes API fixtures and private server configuration", async () => {
  assert.equal(
    Object.values(build.routes).some((route) => route.path === "_test/api"),
    false,
  );
  const assets = await readdir("build/client/assets");
  for (const file of assets.filter((file) => file.endsWith(".js"))) {
    const content = await readFile(`build/client/assets/${file}`, "utf8");
    assert.doesNotMatch(
      content,
      /API_BASE_URL|backend-internal\.invalid|127\.0\.0\.1:4176/,
    );
  }
});
test("fixed Netlify proxy keeps the API prefix and splat", async () => {
  const config = await readFile("netlify.toml", "utf8");
  assert.match(config, /from = "\/api\/\*"/);
  assert.match(
    config,
    /to = "https:\/\/api\.cahierdedoleances\.fr\/api\/:splat"/,
  );
  assert.match(config, /status = 200/);
  const incoming = new URL(
    "http://localhost/api/v1/forms/9007199254740993?q=%C3%A9cole&cursor=a%2Bb",
  );
  const template = config.match(/to = "([^"\n]+\/:splat)"/)[1];
  const target = new URL(
    template.replace(":splat", incoming.pathname.slice("/api/".length)),
  );
  target.search = incoming.search;
  assert.equal(target.pathname, incoming.pathname);
  assert.equal(target.search, incoming.search);
});
