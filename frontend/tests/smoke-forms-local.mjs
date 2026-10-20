// Bounded, read-only recipe against the existing local API; no statistics generation.

import { readFile, writeFile } from "node:fs/promises";
import { createServer } from "node:http";
import { resolve } from "node:path";
import { performance } from "node:perf_hooks";
import { gzipSync } from "node:zlib";
import { chromium, expect } from "@playwright/test";
import { createRequestHandler } from "react-router";

const api = "http://127.0.0.1:8000";
const origin = "http://127.0.0.1:4187";
process.env.API_BASE_URL = api;
const fetchActual = globalThis.fetch;
const apiCalls = [];
globalThis.fetch = async (url, options) => {
  const started = performance.now();
  const response = await fetchActual(url, options);
  if (String(url).startsWith(`${api}/`)) {
    const bytes = await response.arrayBuffer();
    apiCalls.push({
      path: new URL(url).pathname,
      seconds: (performance.now() - started) / 1000,
      bytes: bytes.byteLength,
      status: response.status,
    });
    return new Response(bytes, {
      status: response.status,
      headers: response.headers,
    });
  }
  return response;
};
const build = await import("../build/server/index.js");
const handle = createRequestHandler(build, "production");
const ssr = [];
const server = createServer(async (request, response) => {
  try {
    const url = new URL(request.url, origin);
    if (url.pathname.startsWith("/assets/")) {
      const file = resolve("build/client", `.${url.pathname}`);
      const bytes = await readFile(file);
      response.setHeader(
        "Content-Type",
        file.endsWith(".css")
          ? "text/css"
          : file.endsWith(".js")
            ? "text/javascript"
            : "application/octet-stream",
      );
      response.end(bytes);
      return;
    }
    const start = performance.now();
    const before = apiCalls.length;
    const result = await handle(new Request(url));
    const body = Buffer.from(await result.arrayBuffer());
    const calls = apiCalls.slice(before);
    const total = (performance.now() - start) / 1000;
    ssr.push({
      path: url.pathname,
      status: result.status,
      totalSeconds: total,
      api: calls,
      renderExclusiveSeconds: Math.max(
        0,
        total - calls.reduce((sum, call) => sum + call.seconds, 0),
      ),
      htmlBytes: body.length,
      gzipBytes: gzipSync(body).length,
    });
    response.statusCode = result.status;
    result.headers.forEach((value, key) => {
      response.setHeader(key, value);
    });
    response.end(body);
  } catch {
    response.statusCode = 500;
    response.end("Local recipe error");
  }
});
await new Promise((resolve) => server.listen(4187, "127.0.0.1", resolve));
const browser = await chromium.launch();
const observations = [];
try {
  const listing = await (await fetchActual(`${api}/api/v1/forms`)).json();
  if (listing.length !== 7) throw new Error("Seven local forms expected");
  let totalQuestions = 0;
  for (const javaScriptEnabled of [true, false]) {
    const context = await browser.newContext({ javaScriptEnabled });
    await context.route("**/*", (route) =>
      new URL(route.request().url()).hostname === "127.0.0.1"
        ? route.continue()
        : route.abort(),
    );
    const page = await context.newPage();
    const cdp = await context.newCDPSession(page);
    await cdp.send("Performance.enable");
    const chartRequests = [];
    const errors = [];
    page.on("request", (request) => {
      if (request.url().includes("stats-chart"))
        chartRequests.push(request.url());
    });
    page.on("pageerror", (error) => errors.push(error.message));
    for (const form of javaScriptEnabled
      ? listing
      : listing.filter((f) => ["2", "5"].includes(f.id))) {
      const expected = await (
        await fetchActual(`${api}/api/v1/forms/${form.id}`)
      ).json();
      if (expected.statistics_availability.status !== "available")
        throw new Error("Statistics unavailable");
      const start = performance.now();
      const response = await page.goto(`${origin}/forms/${form.id}`, {
        waitUntil: "load",
      });
      await expect(page.locator('section[id^="question-"]')).toHaveCount(
        expected.questions.length,
      );
      if (response?.status() !== 200) throw new Error("Form page unavailable");
      const loadSeconds = (performance.now() - start) / 1000;
      const ids = await page
        .locator('section[id^="question-"]')
        .evaluateAll((nodes) => nodes.map((node) => node.id));
      if (
        JSON.stringify(ids) !==
        JSON.stringify(expected.questions.map((q) => `question-${q.id}`))
      )
        throw new Error("Question ordering changed");
      const choices = expected.questions.filter((q) =>
        ["single_choice", "multi_choice"].includes(q.type),
      );
      await expect(page.locator("[data-chart-kind]")).toHaveCount(
        choices.length,
      );
      await expect(page.locator("details table")).toHaveCount(choices.length);
      if (javaScriptEnabled) totalQuestions += expected.questions.length;
      const timing = await page.evaluate(() => {
        const n = performance.getEntriesByType("navigation")[0];
        return {
          domContentLoaded: n.domContentLoadedEventEnd,
          load: n.loadEventEnd,
          transferBytes: n.transferSize,
          decodedHtmlBytes: n.decodedBodySize,
          resources: performance.getEntriesByType("resource").map((r) => ({
            name: new URL(r.name).pathname,
            transferBytes: r.transferSize,
            decodedBytes: r.decodedBodySize,
          })),
        };
      });
      const metrics = Object.fromEntries(
        (await cdp.send("Performance.getMetrics")).metrics.map((m) => [
          m.name,
          m.value,
        ]),
      );
      observations.push({
        formId: form.id,
        javaScriptEnabled,
        questions: expected.questions.length,
        charts: choices.length,
        loadSeconds,
        timing,
        cpu: {
          scriptSeconds: metrics.ScriptDuration,
          taskSeconds: metrics.TaskDuration,
          layoutSeconds: metrics.LayoutDuration,
        },
      });
      if (form.id === "2") {
        await page.locator("summary").first().focus();
        await page.keyboard.press("Enter");
        await expect(page.locator("details").first()).toHaveAttribute(
          "open",
          "",
        );
        const before = apiCalls.length;
        await page.locator("summary").first().click();
        await page
          .locator('section[id^="question-"]')
          .first()
          .scrollIntoViewIfNeeded();
        if (apiCalls.length !== before)
          throw new Error("Details or anchor triggered an API call");
        await expect(
          page.locator('[data-chart-kind="yes-no"]').first(),
        ).toBeVisible();
        if (javaScriptEnabled) {
          await page.screenshot({
            path: "/tmp/forms-003-real-desktop.png",
            fullPage: false,
          });
          await page.setViewportSize({ width: 320, height: 800 });
          await page
            .locator('section[id^="question-"]')
            .first()
            .scrollIntoViewIfNeeded();
          await page.screenshot({
            path: "/tmp/forms-003-real-mobile.png",
            fullPage: false,
          });
          if (
            !(await page.evaluate(
              () => document.documentElement.scrollWidth <= window.innerWidth,
            ))
          )
            throw new Error("Mobile overflow");
          await page.setViewportSize({ width: 1280, height: 720 });
        }
      }
    }
    if (chartRequests.length || errors.length)
      throw new Error("Unexpected chart bundle or browser error");
    const before = apiCalls.length;
    const redirected = await fetchActual(`${origin}/forms/2/dashboard`, {
      redirect: "manual",
    });
    if (redirected.status !== 308 || apiCalls.length !== before)
      throw new Error("Legacy redirect failed");
    const qid = listing.find((f) => f.id === "2") ? "2" : null;
    await page.goto(`${origin}/forms/2/dashboard#question-${qid}`);
    await expect(page).toHaveURL(`${origin}/forms/2#question-${qid}`);
    await expect
      .poll(
        async () => (await page.locator(`#question-${qid}`).boundingBox())?.y,
      )
      .toBeLessThan(100);
    // Pages Questions deliberately retain their existing Recharts enhancement.
    await page.locator(`#question-${qid}`).locator("h2 a").click();
    await page.locator("summary").click();
    await expect(page.getByRole("table")).toBeVisible();
    await page.goBack();
    await expect(page).toHaveURL(`${origin}/forms/2#question-${qid}`);
    await context.close();
  }
  if (totalQuestions !== 120) throw new Error("120 questions expected");
  const output = {
    totalQuestions,
    statisticsGeneration: "unchanged",
    chartsOnFormUseRecharts: false,
    observations,
    ssr,
  };
  await writeFile(
    "/tmp/forms-003-local-results.json",
    JSON.stringify(output, null, 2),
  );
  console.log(
    JSON.stringify(
      {
        questions: totalQuestions,
        forms: 7,
        javaScriptModes: 2,
        chartsOnFormUseRecharts: false,
        output: "/tmp/forms-003-local-results.json",
        measurements: observations.map(
          ({
            formId,
            javaScriptEnabled,
            questions,
            charts,
            loadSeconds,
            cpu,
          }) => ({
            formId,
            javaScriptEnabled,
            questions,
            charts,
            loadSeconds,
            cpu,
          }),
        ),
        ssr: ssr.filter((r) => /^\/forms\/\d+$/.test(r.path)),
      },
      null,
      2,
    ),
  );
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
