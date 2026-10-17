import { test, expect } from "@playwright/test";

async function mockApp(page: any, blocked = false, days = 5) {
  const state = { enabled: true, blocked, link: false, linkRequests: 0, paths: [] as string[] };
  await page.route("**/api/v1/**", async (route: any) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    state.paths.push(path);
    let body: any = [];
    if (path === "/auth/me") body = { id: "admin", role: "admin", company_id: "a", full_name: "Admin", is_active: true, financial_blocked: state.blocked };
    if (path === "/company") body = { id: "a", slug: "empresa", trade_name: "Empresa A", operational_profile: "tourism" };
    if (path === "/company/billing/upcoming") body = {
      upcoming: { invoice_kind: "subscription", due_on: "2026-11-18", total_cents: 12900, price_cents: 9900, setup_cents: 0, extra_trips: 2, extra_trip_cents: 1500, is_estimate: true, installment: 3 },
      reminder_enabled: state.enabled, days_until_due: days, show_reminder: state.enabled && days <= 5,
      plan_price_cents: 9900, subscription_status: state.blocked ? "blocked" : "active",
    };
    if (path === "/company/billing/reminder") {
      state.enabled = route.request().postDataJSON().enabled;
      body = { reminder_enabled: state.enabled };
    }
    if (path === "/company/invoices") body = { blocked: state.blocked, invoices: state.blocked ? [{
      id: "invoice", plan_name: "Basic", starts_at: "2026-10-17T03:00:00Z", ends_at: "2026-11-16T03:00:00Z", due_on: "2026-11-18", status: "open", overdue: true,
      price_cents: 9900, extra_trip_cents: 1500, extra_trips: 2, included_trips: 2, used_trips: 4, total_cents: 12900, setup_cents: 0, payment_provider: "infinitepay", payment_url: state.link ? "https://checkout.infinitepay.io/test/payment" : "",
    }] : [] };
    if (path === "/company/invoices/invoice/payment-link") { state.linkRequests++; state.link = true; body = { status: "queued" }; }
    await route.fulfill({ json: body });
  });
  return state;
}

test("five-day notice can be disabled per user and restored from Finance", async ({ page }) => {
  const state = await mockApp(page);
  await page.goto("/");
  const notice = page.getByRole("region", { name: "Aviso de próximo vencimento" });
  await expect(notice).toContainText("18/11/2026");
  await expect(notice).toContainText("129,00");
  await expect(notice.locator("select")).toHaveCount(0);
  await notice.getByRole("button", { name: "Desativar avisos de vencimento para mim" }).click();
  await expect(notice).toHaveCount(0);
  expect(state.enabled).toBe(false);
  await page.reload();
  await expect(notice).toHaveCount(0);
  await page.locator(".sidebar nav").getByRole("button", { name: "Financeiro e cobranças", exact: true }).click();
  const upcoming = page.getByRole("region", { name: "A vencer", exact: true });
  await expect(upcoming.locator(".billing-summary-card")).toHaveCount(5);
  await expect(upcoming).toContainText("3/12");
  await expect(upcoming).toContainText("99,00");
  await expect(upcoming).toContainText("Ativa");
  await upcoming.getByRole("button", { name: "Reativar avisos de vencimento para mim" }).click();
  expect(state.enabled).toBe(true);
  await page.locator(".sidebar nav").getByRole("button", { name: "Visão geral", exact: true }).click();
  await expect(notice).toBeVisible();
});

test("no startup notice before the five-day window", async ({ page }) => {
  await mockApp(page, false, 6);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Visão geral", exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Aviso de próximo vencimento" })).toHaveCount(0);
});

test("blocked administrator has only Finance and can generate payment link", async ({ page }) => {
  const state = await mockApp(page, true);
  await page.goto("/");
  const nav = page.locator(".sidebar nav");
  await expect(nav.getByRole("button")).toHaveText(["Financeiro e cobranças"]);
  await expect(nav.getByRole("link")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Editar cadastro da empresa" })).toHaveCount(0);
  await expect(page.getByText("Bloqueada por pendência", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Gerar link para pagamento", exact: true }).click();
  await expect(page.getByRole("link", { name: "Pagar agora", exact: true })).toHaveAttribute("href", "https://checkout.infinitepay.io/test/payment");
  expect(state.linkRequests).toBe(1);
  expect(state.paths).not.toContain("/users");
  expect(state.paths).not.toContain("/audit");
  state.blocked = false;
  await page.reload();
  await expect(nav.getByRole("button", { name: "Viagens", exact: true })).toBeVisible();
});
