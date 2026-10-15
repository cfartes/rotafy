import { test, expect } from "@playwright/test";

test("admin creates and resends invitations by WhatsApp or both channels", async ({
  page,
}) => {
  let created: any;
  let resent: any;
  const collaborator = {
    id: "driver",
    company_id: "company",
    full_name: "Motorista",
    email: "driver@example.com",
    role: "driver",
    is_active: true,
    contact_phone: "+5547999999999",
  };
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me")
      body = {
        id: "admin",
        company_id: "company",
        role: "admin",
        full_name: "Admin",
        is_active: true,
      };
    else if (path === "/company")
      body = {
        id: "company",
        slug: "agency",
        trade_name: "Agência",
        is_active: true,
      };
    else if (path === "/users") body = [collaborator];
    else if (path === "/users/invitations") {
      created = route.request().postDataJSON();
      body = { id: "new", whatsapp_status: "pending" };
    } else if (path === "/users/driver/invitation") {
      resent = route.request().postDataJSON();
      body = { whatsapp_status: "pending", email_status: "pending" };
    } else if (path === "/users/invitations/whatsapp/status")
      body = [
        {
          id: "message",
          recipient: collaborator.contact_phone,
          status: "uncertain",
          attempts: 1,
          error_code: "send_timeout",
          created_at: "2026-10-15T14:40:26Z",
        },
      ];
    await route.fulfill({ json: body });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Equipe", exact: true }).click();
  await page
    .getByRole("button", { name: "Adicionar pessoa", exact: true })
    .click();
  const create = page.getByRole("dialog", {
    name: "Adicionar à equipe",
    exact: true,
  });
  await create.getByLabel("Nome completo").fill("Novo guia");
  await create.getByLabel("E-mail", { exact: true }).fill("guide@example.com");
  await create
    .getByLabel("Enviar convite para a pessoa definir sua senha")
    .check();
  await create.getByLabel("Enviar convite por").selectOption("whatsapp");
  await expect(create.getByLabel("Senha inicial")).toHaveCount(0);
  await expect(
    create.getByLabel("Telefone/WhatsApp do colaborador"),
  ).toHaveAttribute("required", "");
  await create
    .getByLabel("Telefone/WhatsApp do colaborador")
    .fill("47999999999");
  await create
    .getByRole("button", { name: "Adicionar pessoa", exact: true })
    .click();
  await expect(create).not.toBeVisible();
  expect(created.channel).toBe("whatsapp");
  expect(created.password).toBeUndefined();
  expect(created.contact_phone.replace(/\D/g, "")).toBe("47999999999");
  await page
    .getByRole("button", { name: "Enviar convite", exact: true })
    .click();
  const resend = page.getByRole("dialog", {
    name: "Enviar convite",
    exact: true,
  });
  await expect(
    resend.getByLabel("Telefone/WhatsApp do colaborador"),
  ).toHaveValue(collaborator.contact_phone);
  await resend.getByLabel("Enviar convite por").selectOption("both");
  await resend
    .getByRole("button", { name: "Enviar convite", exact: true })
    .click();
  await expect(resend).not.toBeVisible();
  expect(resent.channel).toBe("both");
  await expect(
    page.getByText("Convites por WhatsApp", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(collaborator.contact_phone, { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "O serviço de WhatsApp não respondeu ao envio dentro do prazo.",
    ),
  ).toBeVisible();
  await expect(page.getByText(/Solicitado em/)).toBeVisible();
});
