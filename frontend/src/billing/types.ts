export type Plan = {
  id: string;
  code: string;
  name: string;
  is_active: boolean;
  created_at: string;
  version_id: string | null;
  version: number | null;
  included_trips: number | null;
  price_cents: number | null;
  extra_trip_cents: number | null;
};
export type PlanVersion = {
  id: string;
  plan_id: string;
  version: number;
  name: string;
  included_trips: number;
  price_cents: number;
  extra_trip_cents: number;
  created_at: string;
};
export type Subscription = {
  trialing?: boolean;
  trial_ends_on?: string | null;
  billing_mode?: string;
  id: string;
  company_id: string;
  plan_id: string;
  plan_name: string;
  plan_code: string;
  starts_on: string;
  status: "active" | "cancelled";
  pending_version_id: string | null;
  pending_effective_at: string | null;
  pending_plan_name: string | null;
  pending_included_trips: number | null;
  pending_price_cents: number | null;
  pending_extra_trip_cents: number | null;
};
export type SubscriptionRow = {
  id: string;
  company_id: string;
  company_name: string;
  status: "active" | "cancelled";
  starts_on: string;
  plan_name: string;
  pending_effective_at: string | null;
  pending_plan_name: string | null;
};
export type Period = {
  is_trial?: boolean;
  id: string;
  subscription_id: string;
  plan_version_id: string;
  starts_at: string;
  ends_at: string;
  cycle_index: number;
  plan_name: string;
  version: number;
  included_trips: number;
  price_cents: number;
  extra_trip_cents: number;
  used_trips: number;
  remaining_trips: number;
  extra_trips: number;
  extras_cents: number;
  total_cents: number;
};
export type Report = {
  subscription: Subscription | null;
  current_period: Period | null;
  upcoming_period: Period | null;
  periods: Period[];
};

export const money = (cents: number) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(
    cents / 100,
  );
export const dateOnly = (value: string) =>
  value.length === 10
    ? value.split("-").reverse().join("/")
    : new Intl.DateTimeFormat("pt-BR", {
        timeZone: "America/Sao_Paulo",
        dateStyle: "short",
      }).format(new Date(value));
export const localToday = () => {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Sao_Paulo",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const get = (type: string) => parts.find((part) => part.type === type)!.value;
  return `${get("year")}-${get("month")}-${get("day")}`;
};
export const moneyInput = (value: number | null) =>
  value === null
    ? ""
    : `${Math.floor(value / 100)},${String(value % 100).padStart(2, "0")}`;
export function parseMoney(value: FormDataEntryValue | null): number {
  const match = String(value || "")
    .trim()
    .match(/^(\d+)(?:[,.](\d{1,2}))?$/);
  if (!match) throw new Error("Informe os valores em reais, como 199,90.");
  const cents =
    Number(match[1]) * 100 + Number((match[2] || "").padEnd(2, "0"));
  if (!Number.isSafeInteger(cents) || cents > 1000000000)
    throw new Error("O valor informado excede o limite permitido.");
  return cents;
}
