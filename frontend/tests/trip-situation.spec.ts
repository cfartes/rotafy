import { test, expect } from "@playwright/test";
import { tripSituation } from "../src/tripSituation";

test("scheduled trips become open at the 48-hour boundary", () => {
  const now = Date.parse("2026-10-21T12:00:00-03:00");
  const trip = (hours: number) => ({ status: "scheduled", starts_at: new Date(now + hours * 3600000).toISOString() });
  expect(tripSituation(trip(49), now)).toBe("scheduled");
  expect(tripSituation(trip(48), now)).toBe("open");
  expect(tripSituation(trip(47), now)).toBe("open");
  expect(tripSituation(trip(-1), now)).toBe("open");
  for (const status of ["in_progress", "completed", "cancelled"]) {
    expect(tripSituation({ ...trip(1), status }, now)).toBe(status);
    expect(tripSituation({ ...trip(72), status }, now)).toBe(status);
  }
});
