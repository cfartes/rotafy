// Executar após generate_documentation.py. Chromium gera os PDFs sem serviço externo.
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";
import fs from "node:fs/promises";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(path.join(root, "frontend", "package.json"));
const { chromium } = require("@playwright/test");
const directory = path.join(root, "frontend", "public", "documentacao");
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  for (const name of ["manual", "manual-superadmin", "apresentacao"]) {
    await page.goto(pathToFileURL(path.join(directory, `${name}.html`)).href);
    await page.evaluate(async () => { await document.fonts.ready; await Promise.all([...document.images].map(image => image.decode())); });
    await page.emulateMedia({ media: "print" });
    await page.pdf({
      path: path.join(directory, `${name}.pdf`),
      printBackground: true,
      preferCSSPageSize: true,
      tagged: true,
      outline: true,
      displayHeaderFooter: name.startsWith("manual"),
      headerTemplate: "<span></span>",
      footerTemplate: '<div style="width:100%;padding:0 16mm;font:9px Arial;color:#526d80;display:flex;justify-content:space-between"><span>Nexus Rotafy · Manual · Edição 2026.10</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>',
    });
    await page.emulateMedia({ media: "screen" });
    console.log(`PDF gerado: ${name}.pdf`);
  }
  const filenames = ["manual.html", "manual.pdf", "manual-superadmin.html", "manual-superadmin.pdf", "apresentacao.html", "apresentacao.pdf", "apresentacao.pptx"];
  const files = await Promise.all(filenames.map(async name => ({ name, bytes: (await fs.stat(path.join(directory, name))).size })));
  await fs.writeFile(path.join(directory, "manifest.json"), JSON.stringify({ edition: "2026.10", revision: 6, revised_at: "2026-10-22", files }, null, 2) + "\n");
} finally { await browser.close(); }
