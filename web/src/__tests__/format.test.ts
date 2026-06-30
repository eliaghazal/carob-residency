import { describe, expect, it } from "vitest";
import { formatMoney, relativeMinutes } from "../format";

describe("formatMoney", () => {
  it("shows minor units as major units with the currency", () => {
    expect(formatMoney(1234567, "USD")).toBe("12,345.67 USD");
    expect(formatMoney(-500, "EUR")).toBe("-5.00 EUR");
  });
});

describe("relativeMinutes", () => {
  const now = Date.parse("2026-06-01T12:00:00Z");
  it("reads future and past times", () => {
    expect(relativeMinutes("2026-06-01T12:12:00Z", now)).toBe("in 12 min");
    expect(relativeMinutes("2026-06-01T11:57:00Z", now)).toBe("3 min ago");
    expect(relativeMinutes("2026-06-01T14:05:00Z", now)).toBe("in 2 h 5 min");
  });
});
