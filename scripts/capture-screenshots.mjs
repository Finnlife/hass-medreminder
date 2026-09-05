/**
 * Capture the panel and the card for the readme.
 *
 * The shots are taken from a standalone harness rather than a running Home
 * Assistant: the harness feeds the real frontend modules a fixed set of demo
 * data and a frozen clock, so a run produces the same images every time and
 * needs neither an instance nor an account.
 *
 * Usage: node scripts/capture-screenshots.mjs [--out docs/screenshots]
 */
import { mkdir, readdir, rm } from "node:fs/promises";
import { createServer } from "node:http";
import { extname, join, resolve } from "node:path";
import { readFile } from "node:fs/promises";
import { chromium } from "playwright";

import { FROZEN_NOW } from "../docs/screenshot/fixture.js";

const ROOT = resolve(import.meta.dirname, "..");
const OUT_INDEX = process.argv.indexOf("--out");
const OUT_DIR = resolve(
  ROOT,
  OUT_INDEX === -1 ? "docs/screenshots" : process.argv[OUT_INDEX + 1],
);

const VIEWPORT = { width: 1280, height: 900 };
const CARD_VIEWPORT = { width: 520, height: 900 };
const LANGUAGES = ["de", "en"];

/** Every shot: the harness view, the file name and how tall the page must be. */
const SHOTS = [
  { view: "overview", name: "overview", themes: ["light", "dark"] },
  { view: "medications", name: "medications", themes: ["light"] },
  { view: "regimens", name: "plans", themes: ["light"] },
  { view: "history", name: "history", themes: ["light"] },
  { view: "card", name: "card", themes: ["light", "dark"], card: true },
];

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".png": "image/png",
  ".json": "application/json",
};

/** Serve the repository so the harness can import the frontend modules. */
function startServer() {
  const server = createServer(async (request, response) => {
    try {
      const url = new URL(request.url, "http://localhost");
      // The panel references its assets under the path Home Assistant serves
      // them from, so the harness has to answer on that path too.
      const path = decodeURIComponent(url.pathname).replace(
        /^\/medication_reminder_frontend\//,
        "/custom_components/medication_reminder/frontend/",
      );
      const file = resolve(ROOT, `.${path}`);
      if (!file.startsWith(ROOT)) {
        response.writeHead(403).end("forbidden");
        return;
      }
      const body = await readFile(file);
      response.writeHead(200, {
        "content-type": MIME[extname(file)] || "application/octet-stream",
      });
      response.end(body);
    } catch (error) {
      response.writeHead(404).end("not found");
    }
  });
  return new Promise((done) => {
    server.listen(0, "127.0.0.1", () => done({ server, port: server.address().port }));
  });
}

async function main() {
  await mkdir(OUT_DIR, { recursive: true });
  const { server, port } = await startServer();
  const browser = await chromium.launch();
  const written = [];

  try {
    for (const shot of SHOTS) {
      for (const language of LANGUAGES) {
        for (const theme of shot.themes) {
          const context = await browser.newContext({
            viewport: shot.card ? CARD_VIEWPORT : VIEWPORT,
            deviceScaleFactor: 2,
            colorScheme: theme === "dark" ? "dark" : "light",
            reducedMotion: "reduce",
          });
          const page = await context.newPage();
          // A frozen clock keeps every relative label stable between runs.
          await page.clock.setFixedTime(new Date(FROZEN_NOW));
          const query = new URLSearchParams({
            view: shot.view, lang: language, theme,
          });
          const errors = [];
          page.on("pageerror", (error) => errors.push(String(error)));
          await page.goto(
            `http://127.0.0.1:${port}/docs/screenshot/harness.html?${query}`,
            { waitUntil: "load" },
          );
          await page.waitForFunction(() => window.__ready === true, null,
            { timeout: 15000 });
          if (errors.length) {
            throw new Error(`${shot.name} (${language}/${theme}): ${errors.join("; ")}`);
          }
          // A missing asset would quietly become a broken-image icon in the
          // published screenshot, so fail the run instead.
          const broken = await page.evaluate(() =>
            [...(window.__component?.shadowRoot?.querySelectorAll("img") || [])]
              .filter((image) => !image.complete || image.naturalWidth === 0)
              .map((image) => image.getAttribute("src")));
          if (broken.length) {
            throw new Error(
              `${shot.name} (${language}/${theme}): images failed to load: ${broken.join(", ")}`,
            );
          }

          const suffix = theme === "dark" ? "-dark" : "";
          const file = join(OUT_DIR, `${shot.name}-${language}${suffix}.png`);
          const target = shot.card
            ? page.locator("#card-stage")
            : page.locator("#panel-stage");
          await target.screenshot({ path: file, animations: "disabled" });
          written.push(file.replace(`${ROOT}\\`, "").replace(`${ROOT}/`, ""));
          await context.close();
        }
      }
    }
  } finally {
    await browser.close();
    server.close();
  }

  // Remove images that no longer belong to any shot, so a renamed view does
  // not leave a stale file behind in the repository.
  const expected = new Set(written.map((file) => file.split(/[\\/]/).pop()));
  for (const name of await readdir(OUT_DIR)) {
    if (name.endsWith(".png") && !expected.has(name)) {
      await rm(join(OUT_DIR, name));
      console.log(`removed stale ${name}`);
    }
  }

  written.forEach((file) => console.log(`wrote ${file}`));
  console.log(`${written.length} screenshots in ${OUT_DIR}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
