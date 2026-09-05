// Generate a small, self-contained icon map for the screenshot harness so the
// capture run needs no npm dependency beyond Playwright.
import { readFileSync, writeFileSync } from "node:fs";
import * as mdi from "@mdi/js";

const names = readFileSync(process.argv[2], "utf8")
  .split("\n").map((line) => line.trim()).filter(Boolean);

const toExport = (name) =>
  "mdi" + name.replace(/^mdi:/, "").split("-")
    .map((part) => part[0].toUpperCase() + part.slice(1)).join("");

const entries = [];
const missing = [];
for (const name of names) {
  const key = toExport(name);
  const path = mdi[key];
  if (!path) { missing.push(`${name} -> ${key}`); continue; }
  entries.push([name, path]);
}
if (missing.length) {
  console.error("Missing icons:", missing);
  process.exit(1);
}

const body = entries.map(([name, path]) => `  "${name}":\n    "${path}",`).join("\n");
const file = `/**
 * Material Design Icons path data used by the screenshot harness.
 *
 * The icons come from the Material Design Icons project by Pictogrammers and
 * are licensed under Apache License 2.0. See https://pictogrammers.com/ for the
 * full set and the license text. Only the icons the panel and the card render
 * are vendored here, so capturing screenshots needs no icon package at run time.
 *
 * Regenerate with: node scripts/generate-icons.mjs
 */
export const ICON_PATHS = Object.freeze({
${body}
});
`;
writeFileSync(OUTPUT, file);
console.log(`wrote ${entries.length} icons to ${OUTPUT}`);
