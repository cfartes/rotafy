import { test, expect } from "@playwright/test";

test("admin opts in to commands and paced 24-hour ticket delivery", async ({
  page,
}) => {
  let submitted: any;
  let config = {
    commands_enabled: false,
    tickets_enabled: false,
    commands: ["qrcode", "onibus", "dados", "embarque", "atendimento"],
    greeting: "Como podemos ajudar?",
    webhook_status: "not_started",
    webhook_error: null,
  };
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me")
      body = {
        id: "admin",
        role: "admin",
        company_id: "company",
        full_name: "Admin",
        is_active: true,
        enabled_modules: ["whatsapp"],
      };
    if (path === "/company")
      body = {
        id: "company",
        slug: "empresa",
        trade_name: "Empresa",
        operational_profile: "tourism",
      };
    if (path === "/company/whatsapp")
      body = {
        status: "connected",
        phone: "+5511999999999",
        send_enabled: true,
      };
    if (path === "/company/whatsapp/automation") {
      if (route.request().method() === "PUT") {
        submitted = route.request().postDataJSON();
        config = { ...config, ...submitted, webhook_status: "pending" };
      }
      body = config;
    }
    if (path === "/company/whatsapp/automation/history")
      body = [
        {
          id: "job",
          kind: "ticket",
          passenger_name: "Maria",
          trip_name: "Praia",
          status: "attention",
          error_code: "ticket_requires_reissue",
        },
        {
          id: "farewell",
          kind: "inactivity",
          passenger_name: null,
          trip_name: null,
          status: "sent",
          error_code: null,
        },
      ];
    await route.fulfill({ json: body });
  });
  await page.goto("/empresa");
  await page.getByRole("button", { name: "WhatsApp", exact: true }).click();
  const commands = page.getByRole("checkbox", {
    name: "Habilitar comandos automáticos no WhatsApp",
  });
  await expect(commands).not.toBeChecked();
  await expect(
    page.getByText("Encerramento por inatividade", { exact: true }),
  ).toBeVisible();
  await commands.check();
  await page
    .getByRole("textbox", { name: "Mensagem do menu" })
    .fill("Olá! Como podemos ajudar?");
  await page
    .getByRole("checkbox", { name: "Minha reserva", exact: true })
    .uncheck();
  await page
    .getByRole("checkbox", { name: /Enviar bilhetes automaticamente 24 horas/ })
    .check();
  await expect(page.getByText(/intervalo mínimo de 3 minutos/)).toBeVisible();
  await page.getByRole("button", { name: "Salvar automações" }).click();
  await expect.poll(() => submitted?.tickets_enabled).toBe(true);
  expect(submitted.commands_enabled).toBe(true);
  expect(submitted.commands).not.toContain("dados");
  await expect(
    page.getByRole("cell", { name: /Precisa de atenção/ }),
  ).toBeVisible();
  await expect(
    page.getByText(/Bilhete antigo sem cópia recuperável/),
  ).toBeVisible();
});

test("attendant sees and closes requests for human service", async ({
  page,
}) => {
  let closed: any;
  let pending = true;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me")
      body = {
        id: "attendant",
        role: "attendant",
        company_id: "company",
        full_name: "Atendente",
        is_active: true,
        enabled_modules: ["whatsapp"],
      };
    if (path === "/company")
      body = { id: "company", slug: "empresa", trade_name: "Empresa" };
    if (path === "/whatsapp/chat/chats")
      body = { chats: [], can_send: true, has_more: false };
    if (path === "/whatsapp/chat/messages")
      body = {
        messages: [],
        deliveries: [],
        next_cursor: null,
        can_send: true,
      };
    if (path === "/whatsapp/chat/handoffs")
      body = pending
        ? [
            {
              chat_id: "5511999999999@c.us",
              phone: "+5511999999999",
              handoff_at: new Date().toISOString(),
            },
          ]
        : [];
    if (path === "/whatsapp/chat/handoffs/close") {
      closed = route.request().postDataJSON();
      pending = false;
      await route.fulfill({ status: 204 });
      return;
    }
    await route.fulfill({ json: body });
  });
  await page.goto("/empresa");
  await page
    .getByRole("button", { name: "Conversas WhatsApp", exact: true })
    .click();
  await expect(page.getByText("Solicitações de atendimento")).toBeVisible();
  await page
    .getByRole("button", { name: "Abrir conversa de +5511999999999" })
    .click();
  await expect(
    page.getByRole("heading", { name: "+5511999999999" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Concluir atendimento de +5511999999999" })
    .click();
  await expect.poll(() => closed?.chat_id).toBe("5511999999999@c.us");
  await expect(page.getByText("Solicitações de atendimento")).toHaveCount(0);
});
