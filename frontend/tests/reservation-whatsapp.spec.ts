import { test, expect } from "@playwright/test";

test("one public QR shows all four contracted journeys", async ({ page }) => {
  const journeys = ["Maragogi", "Maceió", "Praia do Gunga", "Maceió"].map(
    (destination, index) => ({
      leg_id: `leg-${index}`,
      vehicle_name: "Ônibus",
      boarding: "Ponto de embarque",
      dropoff: destination,
      boarding_at: "2027-02-01T11:00:00Z",
      dropoff_at: "2027-02-01T13:00:00Z",
      boarding_status: "waiting",
    }),
  );
  await page.route("**/api/v1/public/ticket", (route) =>
    route.fulfill({
      json: {
        company: { slug: "agency", trade_name: "Agência", has_logo: false },
        is_valid: true,
        ticket: {
          ...journeys[0],
          full_name: "Claudio",
          trip_name: "Pacote de passeios",
          reservation_status: "confirmed",
          trip_status: "scheduled",
        },
        journeys,
      },
    }),
  );
  await page.goto("/bilhete#token=bt.company.placeholder");
  await expect(
    page.getByRole("img", { name: "QR do bilhete individual" }),
  ).toHaveCount(1);
  for (let index = 1; index <= 4; index++)
    await expect(
      page.getByText(`Trecho ${index} · Ônibus`, { exact: true }),
    ).toBeVisible();
});

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
  let sentTicket: any;
  const ticketRows = [
    {
      id: "ticket-1",
      passenger_id: "person-1",
      full_name: "Claudio",
      leg_id: "leg",
      revoked_at: null,
    },
    {
      id: "ticket-2",
      passenger_id: "person-1",
      full_name: "Claudio",
      leg_id: "return",
      revoked_at: null,
    },
    {
      id: "ticket-3",
      passenger_id: "person-2",
      full_name: "Maria",
      leg_id: "leg",
      revoked_at: null,
    },
    {
      id: "ticket-4",
      passenger_id: "person-2",
      full_name: "Maria",
      leg_id: "return",
      revoked_at: null,
    },
  ];
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
    else if (path === "/reservations/booking/tickets") {
      body =
        request.method() === "POST"
          ? {
              issued: ticketRows.map((entry) => ({
                ...entry,
                token: `bt.company.${entry.passenger_id}`,
              })),
            }
          : ticketRows;
    } else if (path === "/tickets/ticket-1/whatsapp") {
      sentTicket = request.postDataJSON();
      body = { id: "ticket-message", status: "pending" };
    } else if (path === "/reservations/booking/whatsapp") {
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
    .getByRole("button", { name: "Viagens e pacotes", exact: true })
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
  await dialog
    .getByRole("button", { name: "Emitir bilhetes", exact: true })
    .click();
  await expect(
    dialog.getByRole("button", { name: "Reemitir bilhete", exact: true }),
  ).toHaveCount(2);
  await expect(
    dialog.getByRole("link", { name: "Abrir bilhete", exact: true }),
  ).toHaveCount(2);
  await dialog
    .getByRole("button", { name: "Enviar bilhete pelo WhatsApp", exact: true })
    .first()
    .click();
  expect(sentTicket.token).toBe("bt.company.person-1");
  expect(sentTicket.operation_key).toMatch(/^[0-9a-f-]{36}$/);
  await expect(
    dialog.getByText(
      "Link do bilhete adicionado à fila de WhatsApp para o telefone da reserva.",
    ),
  ).toBeVisible();
});
