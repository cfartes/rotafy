import { test, expect } from "@playwright/test";

test("company admin connects WhatsApp by QR without knowing session IDs or API keys", async ({
  page,
}) => {
  let status = "created";
  let connectionReads = 0;
  let disconnectRequests = 0;
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
    if (path === "/company/whatsapp") {
      connectionReads++;
      body = { phone: "+5547999999999", status, send_enabled: true };
    }
    if (path === "/company/whatsapp/disconnect") {
      disconnectRequests++;
      status = "disconnected";
      body = { status: "disconnecting" };
    }
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
    page.getByRole("button", { name: "Conectar WhatsApp", exact: true }),
  ).toHaveClass(/button primary/);
  const checkbox = await page.getByRole("checkbox").boundingBox();
  expect(checkbox!.width).toBeLessThanOrEqual(24);
  expect(checkbox!.height).toBeLessThanOrEqual(24);
  await expect(
    page.getByText("Aguardando conexão", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Conectar WhatsApp", exact: true })
    .click();
  expect(submitted).toEqual({ enabled: true });
  await expect(page.locator('input[type="tel"]')).toHaveValue("+5547999999999");
  await expect(page.locator('input[type="tel"]')).toHaveAttribute("readonly", "");
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
  await expect(page.getByRole("button", { name: "Conectar WhatsApp", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Desconectar WhatsApp", exact: true })).toBeVisible();
  await expect(page.getByText(/Atualização desta tela em/)).toHaveCount(0);
  await expect(page.getByText(/Solicitação registrada/)).toHaveCount(0);
  await expect(page.getByRole("checkbox")).toBeDisabled();
  const readsWhenConnected = connectionReads;
  await page.waitForTimeout(5500);
  expect(connectionReads).toBe(readsWhenConnected);
  await page.getByRole("button", { name: "Desconectar WhatsApp", exact: true }).click();
  await expect(page.getByText("Desconectado", { exact: true })).toBeVisible();
  expect(disconnectRequests).toBe(1);
  await expect(page.getByRole("button", { name: "Conectar WhatsApp", exact: true })).toBeVisible();
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

test("admin sees retry countdown, pauses automatic requests and resumes", async ({
  page,
}) => {
  let status = "unavailable";
  let requests = 0;
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
    if (path === "/company/whatsapp/pause") {
      status = "paused";
      body = { status };
    }
    if (path === "/company/whatsapp/connect") {
      status = "pending";
      body = { status };
    }
    if (path === "/company/whatsapp") {
      requests += 1;
      body = {
        phone: "+5547999999999",
        status,
        error_code: status === "unavailable" ? "status_http_404" : null,
        send_enabled: true,
        connect_requested: status !== "paused",
        next_attempt_at: new Date(Date.now() + 40000).toISOString(),
      };
    }
    await route.fulfill({ json: body });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "WhatsApp", exact: true }).click();
  await expect(
    page.getByText(/Próxima tentativa automática em \d+ s/),
  ).toBeVisible();
  await expect(page.getByRole("alert")).toContainText(
    "sessão vinculada não foi encontrada",
  );
  await expect(
    page.getByText("Código de suporte: status_http_404"),
  ).toBeVisible();
  await page.getByRole("button", { name: "Interromper tentativas" }).click();
  await expect(
    page.getByText("Tentativas interrompidas", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/Próxima tentativa automática em/)).toHaveCount(
    0,
  );
  await expect(page.getByText(/Atualização desta tela em/)).toHaveCount(0);
  const pausedRequests = requests;
  await page.waitForTimeout(5500);
  expect(requests).toBe(pausedRequests);
  await page.getByRole("button", { name: "Retomar conexão" }).click();
  await expect(
    page.getByText("Preparando conexão", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Interromper tentativas" }),
  ).toBeVisible();
});
