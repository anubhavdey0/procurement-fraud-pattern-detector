// Copy the sample report into the site so it is served at ./report/assam.html.
// The report is committed once, in docs/sample, and copied here at build time.
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const source = resolve(here, "../../docs/sample/assam-report.html");
const target = resolve(here, "../public/report/assam.html");

if (!existsSync(source)) {
  console.warn(`sample report not found at ${source}; the report link will not resolve`);
} else {
  mkdirSync(dirname(target), { recursive: true });
  copyFileSync(source, target);
}
