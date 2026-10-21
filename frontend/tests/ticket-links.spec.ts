import { test, expect, webkit, type Page } from "@playwright/test";
import { existsSync } from "node:fs";
import { ticketToken, ticketUrl } from "../src/ticketLinks";

const origin = "https://rotafy.example";
const token = "bt.10000000-0000-4000-8000-000000000001.AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8";
const code = "10000000000040008000000000000001aaaqeayeaudaocajbifqydiob4ibceqtcqkrmfyydenbwha5dypq";

test("new ticket URL matches the backend format and preserves the original QR credential", () => {
  const link = ticketUrl(token, origin);
  expect(link).toBe(`${origin}/b/${code}`);
  expect(link).toMatch(/^https:\/\/rotafy\.example\/b\/[a-z0-9]{84}$/);
  expect(ticketToken(link, origin)).toBe(token);
  expect(ticketToken(`${origin}/bilhete#token=${encodeURIComponent(token)}`, origin)).toBe(token);
  expect(ticketToken(token, origin)).toBe(token);
  expect(ticketToken(`${origin}/b/${code.slice(0, -1)}`, origin)).toBe("");
});

async function openTicket(page: Page, baseURL: string) {
  let submitted = "";
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/public/ticket")) {
      submitted = route.request().postDataJSON().token;
      await route.fulfill({ json: { company: { slug: "agency", trade_name: "Agência Exemplo", has_logo: false }, is_valid: true, ticket: { full_name: "Passageiro Exemplo", trip_name: "Maceió x Francês", boarding: "Hotel", dropoff: "Praia", boarding_at: null, dropoff_at: null, boarding_status: "waiting", vehicle_name: "Ônibus" }, journeys: [] } });
    } else await route.fulfill({ status: 401, json: { detail: "Entre novamente" } });
  });
  await page.goto(`${baseURL}/b/${code}`);
  await expect(page.getByRole("heading", { name: "Passageiro Exemplo" })).toBeVisible();
  await expect(page.getByRole("img", { name: "QR do bilhete individual" })).toBeVisible();
  expect(submitted).toBe(token);
  await page.goto(`${baseURL}/bilhete#token=${encodeURIComponent(token)}`);
  await expect(page.getByRole("img", { name: "QR do bilhete individual" })).toBeVisible();
  expect(submitted).toBe(token);
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
