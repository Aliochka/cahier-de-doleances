// Read-only browser checks against the explicitly local documentary preview.
import assert from "node:assert/strict";
import { createReadStream } from "node:fs";
import { readFile } from "node:fs/promises";
import { createInterface } from "node:readline";
import { createGunzip } from "node:zlib";
import { chromium } from "@playwright/test";

const root = new URL("../../", import.meta.url);
const collection = new URL(
  "1789/data/documents/reference-documents-2-7cbcaea79991/",
  root,
);
const config = JSON.parse(
  await readFile(new URL("private/search/phase4/runtime.json", root), "utf8"),
);
const origin = "http://127.0.0.1:3000";
const api = "http://127.0.0.1:8000";
const agen = "ap1789-registry-p1:arcpa_0000-0000_1879_num_1_1_1531";
async function* rows(file) {
  const stream = createInterface({
    input: createReadStream(new URL(file, collection)).pipe(createGunzip()),
    crlfDelay: Infinity,
  });
  for await (const line of stream) yield JSON.parse(line);
}
let agenDocument;
let thematic;
let longest;
let headingCount = 0;
let paragraphLength = 0;
for await (const d of rows("documents.jsonl.gz")) {
  if (d.id === agen) agenDocument = d;
  if (d.id === agen || d.document_kind !== "cahier_autonome_probable") continue;
  const headings = d.xml_blocks.filter(
    (b) => b.role === "section_heading",
  ).length;
  const length = Math.max(
    0,
    ...d.xml_blocks.filter((b) => b.tag === "p").map((b) => b.end - b.start),
  );
  if (headings > headingCount) {
    thematic = d;
    headingCount = headings;
  }
  if (length > paragraphLength) {
    longest = d;
    paragraphLength = length;
  }
}
assert(agenDocument && thematic && longest);
const documents = [agenDocument, thematic, longest];
const units = new Map(documents.map((d) => [d.id, []]));
for await (const u of rows("passages.jsonl.gz")) {
  units.get(u.document_id)?.push(u);
}
const normalize = (s) => s.replace(/\s+/gu, " ").trim();
const browser = await chromium.launch({ headless: true });
const checked = [];
try {
  const page = await browser.newPage({
    viewport: { width: 1280, height: 900 },
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.route("**/*", (route) =>
    new URL(route.request().url()).origin === origin
      ? route.continue()
      : route.abort(),
  );
  for (const d of documents) {
    const docUnits = units.get(d.id).sort((a, b) => a.ordinal - b.ordinal);
    const examples = [
      docUnits[0],
      docUnits[Math.floor(docUnits.length / 2)],
      docUnits.at(-1),
    ];
    for (const u of examples) {
      const path = `/parcourir/1789/reference-documents-2-7cbcaea79991/documents/${encodeURIComponent(d.id)}?unit=${encodeURIComponent(u.id)}`;
      const response = await fetch(
        `${api}/api/v1/documentary/1789/${path.split("/1789/")[1]}`,
        {
          headers: { "x-documentary-preview": config.preview_token },
        },
      );
      assert.equal(response.status, 200);
      const reading = await response.json();
      assert.equal(reading.text_sha256, d.text_sha256);
      assert.equal(reading.blocks.map((b) => b.text).join(""), d.full_text);
      assert.equal(
        reading.paragraphs
          .flatMap((p) => p.fragments)
          .map((f) => f.text)
          .join(""),
        d.full_text,
      );
      const hash = `#passage-${encodeURIComponent(u.id)}`;
      await page.goto(`${origin}${path}${hash}`);
      await page.waitForLoadState("networkidle");
      const region = page.getByRole("region", {
        name: "Texte intégral du cahier",
      });
      const marks = region.locator("mark");
      assert.equal(
        normalize((await marks.allTextContents()).join("")),
        normalize(u.text),
      );
      assert.equal(await region.locator("mark[id]").count(), 1);
      assert.equal(
        await region.locator("mark[id]").getAttribute("id"),
        `passage-${u.id}`,
      );
      assert.equal(
        await region.locator("p, h2").count(),
        reading.paragraphs.length,
      );
      const style = await region.evaluate((node) => {
        const s = getComputedStyle(node);
        return {
          whitespace: s.whiteSpace,
          align: s.textAlign,
          font: s.fontFamily,
        };
      });
      assert.equal(style.whitespace, "normal");
      assert.notEqual(style.align, "justify");
      assert(style.font.includes("Literata"));
      const box = await region.locator("mark[id]").boundingBox();
      assert(box && box.y < 900 && box.y + box.height > 0);
      const markedParagraphs = await marks.count();
      if (d.id === agen && u === examples[0]) {
        // Show the opening prose without changing the actual first-passage check.
        await page.goto(`${origin}${path.split("?")[0]}`);
        await page.screenshot({ path: "/tmp/1789-reading-agen-desktop.png" });
        await page.setViewportSize({ width: 375, height: 900 });
        assert(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth + 2,
          ),
        );
        await page.screenshot({ path: "/tmp/1789-reading-agen-mobile.png" });
        await region.locator("p").first().scrollIntoViewIfNeeded();
        await page.screenshot({
          path: "/tmp/1789-reading-agen-prose-mobile.png",
        });
        await page.setViewportSize({ width: 1280, height: 900 });
      }
      checked.push({
        document: d.id,
        ordinal: u.ordinal,
        markedParagraphs,
      });
    }
  }
  assert.deepEqual(errors, []);
  console.log(
    JSON.stringify({ checked, paragraphLength, headingCount, errors }),
  );
} finally {
  await browser.close();
}
