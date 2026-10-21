import { test, expect } from "@playwright/test";

const company = { id: "company", slug: "empresa", trade_name: "Empresa A", corporate_name: "Empresa A LTDA", cnpj: "52998224725", contact_phone: "+5547999999999", primary_color: "#123456", accent_color: "#abcdef", operational_profile: "tourism", is_active: true, address: "Rua de Teste", address_number: "100", address_complement: "Sala 2", neighborhood: "Centro", city: "Blumenau", state: "SC", postal_code: "89010000" };

test("new company shows and submits all address fields before the operation profile", async ({ page }) => {
  let saved: any;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me") body = { id: "nexus", role: "nexus", full_name: "Nexus", is_active: true };
    if (path === "/nexus/plans") body = [{ id: "plan", name: "Basic", is_active: true, version_id: "version", price_cents: 25990, included_trips: 30, extra_trip_cents: 1000 }];
    if (path === "/nexus/companies" && route.request().method() === "POST") { saved = route.request().postDataJSON(); body = company; }
    await route.fulfill({ json: body });
  });
  await page.goto("/nexus");
  await page.getByRole("button", { name: "Nova empresa", exact: true }).click();
  const dialog = page.getByRole("dialog");
  const section = dialog.locator(".company-address");
  await expect(section.getByText("Endereço da empresa", { exact: true })).toBeVisible();
  for (const label of ["Endereço", "Número", "Bairro", "Cidade", "UF", "CEP"]) {
    await expect(section.getByLabel(label, { exact: true })).toHaveAttribute("required", "");
  }
  await expect(section.getByLabel("Complemento (opcional)")).not.toHaveAttribute("required", "");
  await dialog.getByLabel("Nome comercial", { exact: true }).fill("Empresa A");
  await dialog.getByLabel("Razão social", { exact: true }).fill("Empresa A LTDA");
  await dialog.getByLabel("Identificador de acesso", { exact: true }).fill("empresaexemplo");
  await dialog.locator('input[name="cnpj"]').fill("52998224725");
  await dialog.locator('input[name="contact_phone"]').fill("+5547999999999");
  await section.getByLabel("Endereço", { exact: true }).fill("Rua de Teste");
  await section.getByLabel("Número", { exact: true }).fill("100");
  await section.getByLabel("Bairro", { exact: true }).fill("Centro");
  await section.getByLabel("Cidade", { exact: true }).fill("Blumenau");
  await section.getByLabel("UF", { exact: true }).selectOption("SC");
  await section.getByLabel("CEP", { exact: true }).fill("89010000");
  await expect(section.getByLabel("CEP", { exact: true })).toHaveValue("89010-000");
  await dialog.getByLabel("Perfil operacional", { exact: true }).selectOption("tourism");
  await dialog.locator('select[name="plan_id"]').selectOption("plan");
  await dialog.locator('input[name="full_name"]').fill("Administrador Cliente");
  await dialog.locator('input[name="email"]').fill("cliente@example.com");
  await dialog.locator('input[name="password"]').fill("SenhaExemplo!");
  await dialog.getByRole("button", { name: "Cadastrar empresa", exact: true }).click();
  await expect.poll(() => saved?.postal_code).toBe("89010-000");
  expect(saved).toMatchObject({ address: "Rua de Teste", address_number: "100", address_complement: null, neighborhood: "Centro", city: "Blumenau", state: "SC" });
});

test("company administrator can see and edit the saved address from the company logo", async ({ page }) => {
  let saved: any;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me") body = { id: "admin", role: "admin", company_id: company.id, full_name: "Admin", is_active: true };
    if (path === "/company") { if (route.request().method() === "PATCH") saved = route.request().postDataJSON(); body = { ...company, ...saved }; }
    await route.fulfill({ json: body });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Editar cadastro da empresa" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByLabel("Endereço", { exact: true })).toHaveValue("Rua de Teste");
  await expect(dialog.getByLabel("CEP", { exact: true })).toHaveValue("89010-000");
  await dialog.getByLabel("Endereço", { exact: true }).fill("Rua Atualizada");
  await dialog.getByRole("button", { name: "Salvar cadastro", exact: true }).click();
  await expect.poll(() => saved?.address).toBe("Rua Atualizada");
});

test("a waiting app update never reloads or activates without the user's confirmation", async ({ page }) => {
  await page.addInitScript(() => {
    const messages: unknown[] = [];
    (window as any).updateMessages = messages;
    const registration = Object.assign(new EventTarget(), { waiting: { postMessage: (message: unknown) => messages.push(message) }, installing: null, update: () => Promise.resolve() });
    const worker = Object.assign(new EventTarget(), { getRegistration: () => Promise.resolve(registration), ready: Promise.resolve(registration) });
    Object.defineProperty(navigator, "serviceWorker", { value: worker });
  });
  await page.route("**/api/v1/**", (route) => route.fulfill({ status: 401, json: { detail: "Entre novamente" } }));
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Atualizar aplicativo" })).toBeVisible();
  expect(await page.evaluate(() => (window as any).updateMessages)).toEqual([]);
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.getByRole("button", { name: "Atualizar aplicativo" }).click();
  expect(await page.evaluate(() => (window as any).updateMessages)).toEqual([]);
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Atualizar aplicativo" }).click();
  expect(await page.evaluate(() => (window as any).updateMessages)).toEqual([{ type: "SKIP_WAITING" }]);
});
