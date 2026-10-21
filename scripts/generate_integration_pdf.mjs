import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(path.join(root, "frontend", "package.json"));
const { chromium } = require("@playwright/test");
const directory = path.join(root, "docs", "integracao");
const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  await page.goto(pathToFileURL(path.join(directory, "guia.html")).href);
  await page.emulateMedia({ media: "print" });
  await page.pdf({
    path: path.join(directory, "guia.pdf"), printBackground: true, preferCSSPageSize: true,
    tagged: true, outline: true, displayHeaderFooter: true,
    headerTemplate: "<span></span>",
    footerTemplate: '<div style="width:100%;padding:0 14mm;font:8px Arial;color:#526d80;display:flex;justify-content:space-between"><span>Nexus Rotafy · Integração · 21/10/2026</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>',
  });
  console.log("PDF de integração gerado.");
} finally { await browser.close(); }
