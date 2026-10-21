import { test, expect, webkit, type Page } from "@playwright/test";
import { existsSync } from "node:fs";
import { createServer } from "node:http";
import type { AddressInfo } from "node:net";
import { ticketToken, ticketUrl } from "../src/ticketLinks";

const origin = "https://rotafy.example";
const token = "bt.10000000-0000-4000-8000-000000000001.AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8";
const code = "10000000000040008000000000000001aaaqeayeaudaocajbifqydiob4ibceqtcqkrmfyydenbwha5dypq";

test("new ticket URL matches the backend format and preserves the original QR credential", () => {
  const link = ticketUrl(token, origin);
  expect(link).toBe(`${origin}/api/v1/public/bilhete/${code}`);
  expect(link).toMatch(/^https:\/\/rotafy\.example\/api\/v1\/public\/bilhete\/[a-z0-9]{84}$/);
  expect(ticketToken(link, origin)).toBe(token);
  expect(ticketToken(`${origin}/bilhete#token=${encodeURIComponent(token)}`, origin)).toBe(token);
  expect(ticketToken(token, origin)).toBe(token);
  expect(ticketToken(`${origin}/b/${code.slice(0, -1)}`, origin)).toBe("");
});

async function openTicket(page: Page, baseURL: string) {
  // WebKit cannot mock a redirect with route.fulfill; exercise real HTTP here.
  const redirectServer = createServer((_request, response) => {
    response.writeHead(303, { Location: `${baseURL}/bilhete#token=${encodeURIComponent(token)}`, "Cache-Control": "no-store" }); response.end();
  });
  await new Promise<void>((resolve) => redirectServer.listen(0, "127.0.0.1", resolve));
  const redirectBase = `http://127.0.0.1:${(redirectServer.address() as AddressInfo).port}`;
  try {
  let submitted = "";
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.includes("/public/bilhete/")) {
      await route.continue();
    } else if (path.endsWith("/public/ticket")) {
      submitted = route.request().postDataJSON().token;
      await route.fulfill({ json: { company: { slug: "agency", trade_name: "Agência Exemplo", has_logo: false }, is_valid: true, ticket: { full_name: "Passageiro Exemplo", trip_name: "Maceió x Francês", boarding: "Hotel", dropoff: "Praia", boarding_at: null, dropoff_at: null, boarding_status: "waiting", vehicle_name: "Ônibus" }, journeys: [] } });
    } else await route.fulfill({ status: 401, json: { detail: "Entre novamente" } });
  });
  await page.goto(`${redirectBase}/api/v1/public/bilhete/${code}`);
  await expect(page).toHaveURL(new RegExp("/bilhete#token="));
  await expect(page.getByRole("heading", { name: "Passageiro Exemplo" })).toBeVisible();
  await expect(page.getByRole("img", { name: "QR do bilhete individual" })).toBeVisible();
  expect(submitted).toBe(token);
  await page.goto(`${baseURL}/bilhete#token=${encodeURIComponent(token)}`);
  await expect(page.getByRole("img", { name: "QR do bilhete individual" })).toBeVisible();
  expect(submitted).toBe(token);
  } finally {
    redirectServer.closeAllConnections();
    await new Promise<void>((resolve) => redirectServer.close(() => resolve()));
  }
}

test("new and old ticket links open in Chromium on a mobile viewport", async ({ page, baseURL }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openTicket(page, baseURL!);
});

test("new and old ticket links open in WebKit on a mobile viewport", async ({ baseURL }) => {
  test.skip(!existsSync(webkit.executablePath()), "Install WebKit with npx playwright install webkit");
  const browser = await webkit.launch();
  try {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
    await openTicket(await context.newPage(), baseURL!);
  } finally { await browser.close(); }
});


test("the public ticket redirect works even when an old cached app opens unknown paths as the portal", async ({ page }) => {
  const legacy = `<!doctype html><html><body><h1 id="screen"></h1><script>document.getElementById('screen').textContent=location.pathname==='/bilhete'&&new URLSearchParams(location.hash.slice(1)).get('token')===${JSON.stringify(token)}?'Bilhete de embarque':'Acesso ao portal';</script></body></html>`;
  const server = createServer((request, response) => {
    if (request.url === "/old-worker.js") {
      response.writeHead(200, { "Content-Type": "application/javascript" });
      response.end(`self.addEventListener('install',()=>self.skipWaiting());self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));self.addEventListener('fetch',e=>{if(e.request.mode==='navigate'&&!new URL(e.request.url).pathname.startsWith('/api/'))e.respondWith(Promise.resolve(new Response(${JSON.stringify(legacy)},{headers:{'Content-Type':'text/html'}})));});`);
    } else if (request.url === `/api/v1/public/bilhete/${code}`) {
      response.writeHead(303, { Location: `/bilhete#token=${encodeURIComponent(token)}`, "Cache-Control": "no-store" }); response.end();
    } else { response.writeHead(200, { "Content-Type": "text/html" }); response.end(legacy); }
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
  try {
    await page.goto(base);
    await page.evaluate(async () => {
      await navigator.serviceWorker.register("/old-worker.js");
      await navigator.serviceWorker.ready;
      if (!navigator.serviceWorker.controller) await new Promise<void>((resolve) => navigator.serviceWorker.addEventListener("controllerchange", () => resolve(), { once: true }));
    });
    await page.goto(`${base}/b/${code}`);
    await expect(page.getByRole("heading", { name: "Acesso ao portal" })).toBeVisible();
    await page.goto(`${base}/api/v1/public/bilhete/${code}`);
    await expect(page.getByRole("heading", { name: "Bilhete de embarque" })).toBeVisible();
    await expect(page).toHaveURL(/\/bilhete#token=/);
  } finally {
    server.closeAllConnections();
    await new Promise<void>((resolve) => server.close(() => resolve()));
  }
});
