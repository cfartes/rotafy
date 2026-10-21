import { test, expect, type Page } from "@playwright/test";

const company = { id: "company", slug: "empresa", trade_name: "Empresa", corporate_name: "Empresa LTDA", operational_profile: "tourism", address: "Rua atual", address_number: "100", address_complement: "Sala 2", neighborhood: "Centro", city: "Blumenau", state: "SC", postal_code: "89010000" };
const found = { address: "Praça da Sé", neighborhood: "Sé", city: "São Paulo", state: "SP" };
async function openCompany(page: Page) {
  await page.route("**/api/v1/**", async route => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    await route.fulfill({ json: path === "/auth/me" ? { id: "admin", role: "admin", company_id: "company", full_name: "Admin", is_active: true } : path === "/company" ? company : [] });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Editar cadastro da empresa" }).click();
}

test("CEP comes first and fills the address without changing number or complement", async ({ page }) => {
  await openCompany(page);
  await page.route("**/locations/postal-code/01001000", route => route.fulfill({ json: found }));
  const fields = page.getByRole("dialog").locator(".company-address");
  await expect(fields.locator("input").first()).toHaveAttribute("name", "postal_code");
  await fields.getByLabel("CEP", { exact: true }).fill("01001000");
  await expect(fields.getByLabel("Endereço", { exact: true })).toHaveValue("Praça da Sé");
  await expect(fields.getByLabel("Bairro", { exact: true })).toHaveValue("Sé");
  await expect(fields.getByLabel("Cidade", { exact: true })).toHaveValue("São Paulo");
  await expect(fields.getByLabel("UF", { exact: true })).toHaveValue("SP");
  await expect(fields.getByLabel("Número", { exact: true })).toHaveValue("100");
  await expect(fields.getByLabel("Complemento (opcional)")).toHaveValue("Sala 2");
  await fields.getByLabel("Endereço", { exact: true }).fill("Endereço corrigido");
  await expect(fields.getByLabel("Endereço", { exact: true })).toHaveValue("Endereço corrigido");
});

test("a manual correction made while the CEP is loading wins over the late response", async ({ page }) => {
  await openCompany(page);
  let finish: (() => void) | undefined;
  await page.route("**/locations/postal-code/01001000", async route => {
    await new Promise<void>(resolve => { finish = resolve; });
    await route.fulfill({ json: found });
  });
  const fields = page.getByRole("dialog").locator(".company-address");
  await fields.getByLabel("CEP", { exact: true }).fill("01001000");
  await expect.poll(() => !!finish).toBe(true);
  await fields.getByLabel("Endereço", { exact: true }).fill("Entrada pela rua lateral");
  finish!();
  await expect(fields.getByLabel("Cidade", { exact: true })).toHaveValue("São Paulo");
  await expect(fields.getByLabel("Endereço", { exact: true })).toHaveValue("Entrada pela rua lateral");
});

test("missing CEP leaves address fields available for manual entry", async ({ page }) => {
  await openCompany(page);
  await page.route("**/locations/postal-code/99999999", route => route.fulfill({ status: 404, json: { detail: "CEP não encontrado. Preencha o endereço manualmente." } }));
  const fields = page.getByRole("dialog").locator(".company-address");
  await fields.getByLabel("CEP", { exact: true }).fill("99999999");
  await expect(fields.getByRole("status")).toContainText("CEP não encontrado");
  await fields.getByLabel("Endereço", { exact: true }).fill("Rua informada pelo cliente");
  await expect(fields.getByLabel("Endereço", { exact: true })).toHaveValue("Rua informada pelo cliente");
});
