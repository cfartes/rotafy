import { test, expect } from "@playwright/test";

test("attendant sees uncertain delivery and can queue an explicit reservation summary", async ({
  page,
}) => {
  const future = "2027-02-01T11:00:00Z";
  const trip = {
    id: "trip",
    name: "Passeio",
    destination: "Praia",
    status: "scheduled",
    mode: "one_way",
    price_cents: 10000,
    starts_at: future,
    ends_at: "2027-02-01T13:00:00Z",
    vehicle_count: 1,
    capacity: 10,
    legs: [
      {
        id: "leg",
        origin: "Maceió",
        destination: "Praia",
        starts_at: future,
        ends_at: "2027-02-01T13:00:00Z",
        stops: [],
      },
    ],
    vehicles: [],
    completion: null,
  };
  const booking = {
    id: "booking",
    contact_name: "Família Teste",
    phone: "+5511999999999",
    status: "confirmed",
    is_paid: false,
    passenger_count: 1,
    vehicle_name: "Ônibus",
    total_cents: 10000,
    allocation_id: "allocation",
    passengers: [],
    journeys: [],
    edit_version: 0,
  };
  const history: any[] = [
    {
      id: "message",
      kind: "confirmed",
      status: "uncertain",
      created_at: future,
      sent_at: null,
      attempts: 1,
      error_code: "acceptance_unknown",
    },
  ];
  let submitted: any;
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request(),
      path = new URL(request.url()).pathname.replace("/api/v1", "");
    let body: any = [];
    if (path === "/auth/me")
      body = {
        id: "user",
        company_id: "company",
        role: "attendant",
        full_name: "Atendente",
        is_active: true,
      };
    else if (path === "/company")
      body = {
        id: "company",
        slug: "agencia",
        trade_name: "Agência",
        is_active: true,
      };
    else if (path === "/trips") body = [trip];
    else if (path === "/trips/trip") body = trip;
    else if (path === "/trips/trip/reservations") body = [booking];
    else if (path === "/reservations/booking") body = booking;
    else if (path.endsWith("/availability"))
      body = {
        vehicles: [],
        can_book: true,
        message: "",
        suggested_allocation_id: null,
      };
    else if (path === "/reservations/booking/whatsapp") {
      if (request.method() === "POST") {
        submitted = request.postDataJSON();
        history.push({
          id: "manual",
          kind: "manual",
          status: "pending",
          attempts: 0,
          created_at: future,
        });
        body = { id: "manual", status: "pending" };
      } else body = history;
    }
    await route.fulfill({ json: body });
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: "Frota, pacotes e viagens", exact: true })
    .click();
  await page.getByRole("button", { name: "Detalhes", exact: true }).click();
  await page
    .getByRole("button", { name: "Reservas e lugares", exact: true })
    .click();
  await page.getByRole("button", { name: "Ver reserva", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Detalhes da reserva" });
  await expect(
    dialog.getByText("Envio incerto · confira antes de reenviar", {
      exact: false,
    }),
  ).toBeVisible();
  await dialog
    .getByRole("button", { name: "Enviar resumo pelo WhatsApp" })
    .click();
  await expect(dialog.getByText("Mensagem adicionada à fila.")).toBeVisible();
  expect(submitted.operation_key).toMatch(/^[0-9a-f-]{36}$/);
  await expect(
    dialog.getByText("Resumo manual", { exact: true }),
  ).toBeVisible();
});
