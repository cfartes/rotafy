import { test, expect } from "@playwright/test";

test("plan addendum is read and email-confirmed separately from the original contract", async ({ page }) => {
  let signed = false, viewed = false;
  const company = { id: "a", slug: "empresa", trade_name: "Empresa A", corporate_name: "Empresa A LTDA", cnpj: "52998224725", contact_phone: "+5547999999999", primary_color: "#123456", accent_color: "#abcdef", operational_profile: "tourism", address: "Rua de Teste", address_number: "100", address_complement: "", neighborhood: "Centro", city: "Blumenau", state: "SC", postal_code: "89010000" };
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me") body = { id: "admin", role: "admin", full_name: "Representante Cliente", email: "cliente@example.com", company_id: "a", is_active: true, contract_pending: false };
    if (path === "/company") body = company;
    if (path === "/company/contract") body = { required: true, pending: false, acceptance: { document_id: "original", sha256: "a".repeat(64), accepted_at: "2026-10-21T15:00:00Z", email: "cliente@example.com", email_status: "sent", code: "2026-r2" } };
    if (path === "/company/contract/plan-changes") body = [{ id: "change", status: signed ? "accepted" : "awaiting", effective_at: "2026-11-20T03:00:00Z", old_plan_name: "Basic", plan_name: "Professional", price_cents: 29900, included_trips: 20, extra_trip_cents: 1500, invitation_status: "sent", document_id: signed ? "addendum" : null, sha256: signed ? "b".repeat(64) : null, email: "cliente@example.com", copy_status: "pending" }];
    if (path === "/company/contract/plan-changes/change/prepare") body = { id: "addendum", sha256: "b".repeat(64), content: "ADITIVO: Basic para Professional. Mensalidade R$ 299,00. Vigência no próximo ciclo, sem novo setup." };
    if (path === "/company/contract/viewed") { viewed = true; body = { viewed: true }; }
    if (path === "/company/contract/code") { expect(viewed).toBe(true); body = { email: "cliente@example.com", status: "queued" }; }
    if (path === "/company/contract/accept") { expect(route.request().postDataJSON()).toEqual({ document_id: "addendum", sha256: "b".repeat(64), code: "123456", accepted: true }); signed = true; body = { accepted: true }; }
    await route.fulfill({ json: body });
  });
  await page.goto("/?view=contract");
  await expect(page.getByRole("link", { name: "Baixar contrato aceito", exact: true })).toHaveAttribute("href", "/api/v1/company/contract/documents/original/pdf");
  await page.getByRole("button", { name: "Conferir e ler aditivo" }).click();
  await page.getByLabel("CPF do representante", { exact: true }).fill("52998224725");
  await page.getByLabel("Função do representante", { exact: true }).fill("Administrador");
  await page.getByRole("checkbox", { name: "Declaro que tenho poderes para representar esta empresa." }).check();
  await page.getByRole("button", { name: "Conferir dados e preparar aditivo" }).click();
  await expect(page.getByRole("button", { name: "Confirmar aceite do aditivo" })).toBeDisabled();
  await page.getByRole("button", { name: "Ler aditivo completo" }).click();
  await expect(page.getByRole("article", { name: "Texto integral do contrato" })).toContainText("Basic para Professional");
  await page.getByRole("button", { name: "Voltar para confirmar o aceite" }).click();
  await page.getByRole("button", { name: "Enviar código de confirmação por e-mail" }).click();
  await page.getByLabel("Código recebido por e-mail").fill("123456");
  await page.getByRole("checkbox", { name: "Li e aceito o contrato integral apresentado e declaro poderes para representar a empresa." }).check();
  await page.getByRole("button", { name: "Confirmar aceite do aditivo" }).click();
  await expect(page.getByRole("link", { name: "Baixar aditivo aceito" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Baixar contrato aceito", exact: true })).toHaveAttribute("href", "/api/v1/company/contract/documents/original/pdf");
});

test("client reads and downloads contract before unchecked acceptance and email confirmation", async ({ page }) => {
  let pending = true;
  let viewed = false;
  let accepted: any;
  let address: any;
  const hash = "a".repeat(64);
  const company = { id: "a", slug: "empresa", trade_name: "Empresa A", corporate_name: "Empresa A LTDA", cnpj: "52998224725", contact_phone: "+5547999999999", primary_color: "#123456", accent_color: "#abcdef", operational_profile: "tourism", address: "Rua de Teste", address_number: "100", address_complement: "", neighborhood: "Centro", city: "Blumenau", state: "SC", postal_code: "89010000" };
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me") body = { id: "admin", role: "admin", full_name: "Representante Cliente", email: "cliente@example.com", company_id: "a", is_active: true, contract_pending: pending };
    if (path === "/company") { if (route.request().method() === "PATCH") address = route.request().postDataJSON(); body = company; }
    if (path === "/company/contract/prepare") body = { id: "document", sha256: hash, content: "CONTRATO INTEGRAL PARA LEITURA\n\nEmpresa A LTDA\n\nCláusulas e condições comerciais preservadas." };
    if (path === "/company/contract/viewed") { viewed = true; body = { viewed: true }; }
    if (path === "/company/contract/code") { expect(viewed).toBe(true); body = { email: "cliente@example.com", status: "queued" }; }
    if (path === "/company/contract/accept") { accepted = route.request().postDataJSON(); pending = false; body = { accepted: true }; }
    if (path === "/company/contract") body = { required: true, pending, acceptance: pending ? null : { document_id: "document", sha256: hash, accepted_at: "2026-10-21T15:00:00Z", email: "cliente@example.com", email_status: "pending", code: "2026-r1" } };
    await route.fulfill({ json: body });
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Leia e aceite o contrato de utilização" })).toBeVisible();
  await expect(page.locator(".sidebar")).toHaveCount(0);
  await page.getByLabel("CPF do representante", { exact: true }).fill("52998224725");
  await page.getByLabel("Função do representante", { exact: true }).fill("Administrador");
  await page.getByRole("checkbox", { name: "Declaro que tenho poderes para representar esta empresa." }).check();
  await page.getByRole("button", { name: "Conferir dados e preparar contrato" }).click();
  await expect(page.getByRole("link", { name: "Baixar PDF antes de aceitar" })).toHaveAttribute("href", "/api/v1/company/contract/documents/document/pdf");
  const consent = page.getByRole("checkbox", { name: "Li e aceito o contrato integral apresentado e declaro poderes para representar a empresa." });
  await expect(consent).not.toBeChecked();
  await expect(page.getByRole("button", { name: "Confirmar aceite do contrato" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Enviar código de confirmação por e-mail" })).toBeDisabled();
  await page.getByRole("button", { name: "Ler contrato completo" }).click();
  await expect(page.getByRole("article", { name: "Texto integral do contrato" })).toContainText("CONTRATO INTEGRAL PARA LEITURA");
  await page.getByRole("button", { name: "Voltar para confirmar o aceite" }).click();
  await page.getByRole("button", { name: "Enviar código de confirmação por e-mail" }).click();
  await page.getByLabel("Código recebido por e-mail").fill("123456");
  await consent.check();
  await page.getByRole("button", { name: "Confirmar aceite do contrato" }).click();
  await expect(page.locator(".sidebar")).toBeVisible();
  expect(address.state).toBe("SC");
  expect(accepted).toEqual({ document_id: "document", sha256: hash, code: "123456", accepted: true });
  await page.getByRole("button", { name: "Meu contrato", exact: true }).click();
  await expect(page.getByRole("link", { name: "Baixar contrato aceito" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Baixar comprovante do aceite" })).toBeVisible();
});

test("new version is a draft until the full Nexus administrator explicitly approves publication", async ({ page }) => {
  let published = 0;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me") body = { id: "nexus", role: "nexus", full_name: "Nexus", is_active: true };
    if (path === "/nexus/integrations") body = { version: 1, openwa_key_configured: false, resend_key_configured: false, email_from: "nexus@example.com", openwa_base_url: "https://example.com" };
    if (path === "/nexus/billing/settings") body = { version: 1 };
    if (path === "/nexus/contracts") body = { active_version_id: null, versions: [{ id: "draft", code: "2026-r1", title: "Contrato Rotafy", body: "Texto integral da minuta para conferência e aprovação.", sha256: "b".repeat(64), status: "draft" }] };
    if (path.endsWith("/publish")) published++;
    await route.fulfill({ json: body });
  });
  await page.goto("/nexus");
  await page.getByRole("button", { name: "Configurações", exact: true }).click();
  await expect(page.getByText("Rascunho para aprovação", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Publicar versão aprovada" })).toBeDisabled();
  expect(published).toBe(0);
});
