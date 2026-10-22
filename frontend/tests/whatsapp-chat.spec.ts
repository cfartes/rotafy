import { test, expect } from "@playwright/test";

test("company conversations support replies without choosing a provider session", async ({
  page,
}) => {
  let sent: any;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me")
      body = {
        id: "admin",
        role: "admin",
        full_name: "Admin",
        company_id: "company",
        is_active: true,
        enabled_modules: ["whatsapp"],
      };
    if (path === "/company")
      body = {
        id: "company",
        slug: "empresa",
        trade_name: "Empresa teste",
        is_active: true,
      };
    if (path === "/whatsapp/chat/chats")
      body = {
        chats: [
          {
            id: "5547999999999@c.us",
            name: "Maria",
            preview: "Bom dia",
            timestamp: 1792670000,
            unread_count: 1,
            is_group: false,
          },
        ],
        has_more: false,
        can_send: true,
      };
    if (path === "/whatsapp/chat/messages")
      body = {
        messages: [
          {
            id: "message1",
            body: "Bom dia",
            type: "chat",
            timestamp: 1792670000,
            from_me: false,
            status: "delivered",
            author: "",
            has_media: false,
          },
        ],
        deliveries: [],
        next_cursor: null,
        can_send: true,
      };
    if (path === "/whatsapp/chat/send") {
      sent = route.request().postDataJSON();
      body = { id: "delivery1", status: "pending" };
    }
    await route.fulfill({ json: body });
  });
  await page.goto("/empresa");
  await page
    .getByRole("button", { name: "Conversas WhatsApp", exact: true })
    .click();
  await page.getByRole("button", { name: /Maria/ }).click();
  await expect(page.getByLabel("Histórico da conversa")).toContainText(
    "Bom dia",
  );
  await page.getByLabel("Responder à mensagem Bom dia").click();
  await page
    .getByRole("textbox", { name: "Mensagem", exact: true })
    .fill("Olá, Maria!");
  await page
    .getByRole("button", { name: "Enviar mensagem", exact: true })
    .click();
  await expect.poll(() => sent?.text).toBe("Olá, Maria!");
  expect(sent.quoted_message_id).toBe("message1");
  expect(sent.session_id).toBeUndefined();
  expect(sent.operation_key).toMatch(/^[0-9a-f-]{36}$/);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByLabel("Voltar às conversas")).toBeVisible();
  await page.getByLabel("Voltar às conversas").click();
  await expect(page.getByLabel("Pesquisar conversas")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

test("superadmin can diagnose provider outage and request session recovery", async ({
  page,
}) => {
  let action: any;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me")
      body = {
        id: "nexus",
        role: "nexus",
        full_name: "Nexus",
        company_id: null,
        is_active: true,
      };
    if (path === "/nexus/whatsapp/connections")
      body = {
        service: {
          status: "unavailable",
          checked_at: new Date().toISOString(),
        },
        companies: [
          {
            id: "company",
            trade_name: "Empresa teste",
            slug: "empresa",
            contact_phone: "+5547999999999",
            is_active: true,
            module_enabled: true,
            enabled: false,
            status: "unavailable",
            provider_status: "unknown",
            session_id: "session",
            disconnect_requested: false,
            restart_requested: false,
          },
        ],
      };
    if (path.endsWith("/company/action")) {
      action = route.request().postDataJSON();
      body = { status: "pending" };
    }
    await route.fulfill({ json: body });
  });
  await page.goto("/nexus");
  await page
    .getByRole("button", { name: "Conexões WhatsApp", exact: true })
    .click();
  await expect(page.getByText("Empresa teste", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Retomar conexão", exact: true })
    .click();
  await expect.poll(() => action?.action).toBe("reconnect");
  expect(action.enable_sends).toBe(false);
  page.once("dialog", (d) => d.accept());
  await page
    .getByRole("button", { name: "Reiniciar sessão", exact: true })
    .click();
  await expect.poll(() => action?.action).toBe("restart");
});
