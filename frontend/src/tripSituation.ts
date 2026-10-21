export function tripSituation(trip: { status: string; starts_at: string }, now = Date.now()): string {
  if (trip.status !== "scheduled") return trip.status;
  return new Date(trip.starts_at).getTime() - now <= 48 * 60 * 60 * 1000 ? "open" : "scheduled";
}
