/**
 * Regenerate the vendored icon map for the screenshot harness.
 *
 * Collects every `mdi:` icon the panel and the card reference and writes their
 * path data to docs/screenshot/icons.js, so capturing screenshots needs no icon
 * package at run time. It fails on a name Material Design Icons does not know,
 * which is worth knowing: an unknown name renders as an empty box in Home
 * Assistant without any error.
 *
 * Usage: npm install --no-save @mdi/js && node scripts/generate-icons.mjs
 */
import { readFileSync, readdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import * as mdi from "@mdi/js";

const ROOT = resolve(import.meta.dirname, "..");
const FRONTEND = resolve(ROOT, "custom_components/medication_reminder/frontend");
const OUTPUT = resolve(ROOT, "docs/screenshot/icons.js");

const names = [
  ...new Set(
    readdirSync(FRONTEND)
      .filter((file) => file.endsWith(".js"))
      .flatMap((file) =>
        readFileSync(resolve(FRONTEND, file), "utf8").match(/mdi:[a-z0-9-]+/g) || []),
  ),
].sort();

const toExport = (name) =>
  "mdi" + name.replace(/^mdi:/, "").split("-")
    .map((part) => part[0].toUpperCase() + part.slice(1)).join("");

const entries = [];
const missing = [];
for (const name of names) {
  const path = mdi[toExport(name)];
  if (path) entries.push([name, path]);
  else missing.push(`${name} -> ${toExport(name)}`);
}
if (missing.length) {
  console.error("Material Design Icons has no such icon:", missing.join(", "));
  process.exit(1);
}

const body = entries.map(([name, path]) => `  "${name}":\n    "${path}",`).join("\n");
writeFileSync(
  OUTPUT,
  `/**
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
`,
);
console.log(`wrote ${entries.length} icons to ${OUTPUT}`);
