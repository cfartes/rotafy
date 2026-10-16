import { test, expect } from "@playwright/test";

test("company admin connects WhatsApp by QR without knowing session IDs or API keys", async ({
  page,
}) => {
  let status = "created";
  let submitted: any;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me")
      body = {
        id: "admin",
        role: "admin",
        company_id: "a",
        full_name: "Admin",
        is_active: true,
      };
    if (path === "/company")
      body = {
        id: "a",
        slug: "a",
        trade_name: "Empresa A",
        operational_profile: "tourism",
      };
    if (path === "/company/whatsapp")
      body = { phone: "+5547999999999", status, send_enabled: true };
    if (path === "/company/whatsapp/connect") {
      submitted = route.request().postDataJSON();
      status = "qr_ready";
      body = { status: "pending" };
    }
    if (path === "/company/whatsapp/qr")
      body = {
        qr_code:
          "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jVn8AAAAASUVORK5CYII=",
      };
    await route.fulfill({ json: body });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "WhatsApp", exact: true }).click();
  await expect(
    page.getByText("Aguardando conexão", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Conectar WhatsApp", exact: true })
    .click();
  expect(submitted).toEqual({ contact_phone: "+5547999999999", enabled: true });
  await expect(
    page.getByRole("img", {
      name: "QR Code para conectar o WhatsApp da empresa",
    }),
  ).toBeVisible();
  await expect(
    page.getByText("Escaneie o QR Code", { exact: true }),
  ).toBeVisible();
  status = "connected";
  await expect(page.getByText("Conectado", { exact: true })).toBeVisible({
    timeout: 10000,
  });
  await expect(
    page.getByRole("img", {
      name: "QR Code para conectar o WhatsApp da empresa",
    }),
  ).toHaveCount(0);
  await expect(
    page.getByText("Envios habilitados.", { exact: false }),
  ).toBeVisible();
});

test("attendant cannot see company WhatsApp connection menu", async ({
  page,
}) => {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me")
      body = {
        id: "attendant",
        role: "attendant",
        company_id: "a",
        full_name: "Atendente",
        is_active: true,
      };
    if (path === "/company")
      body = {
        id: "a",
        slug: "a",
        trade_name: "Empresa A",
        operational_profile: "regular",
      };
    await route.fulfill({ json: body });
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Visão geral", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "WhatsApp", exact: true }),
  ).toHaveCount(0);
});

test("company sees number mismatch as a suspended connection instead of a success", async ({
  page,
}) => {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me")
      body = {
        id: "admin",
        role: "admin",
        company_id: "a",
        full_name: "Admin",
        is_active: true,
      };
    if (path === "/company")
      body = {
        id: "a",
        slug: "a",
        trade_name: "Empresa A",
        operational_profile: "tourism",
      };
    if (path === "/company/whatsapp")
      body = {
        phone: "+5547999999999",
        status: "wrong_number",
        send_enabled: true,
      };
    await route.fulfill({ json: body });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "WhatsApp", exact: true }).click();
  await expect(
    page.getByText("Número conectado diferente do informado", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("alert")).toContainText(
    "Os envios estão suspensos",
  );
  await expect(page.getByRole("img")).toHaveCount(0);
});
