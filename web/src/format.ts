// Formatting shared by every view. Money arrives as integer minor units.

const MINOR_UNITS: Record<string, number> = { USD: 2, EUR: 2, LBP: 2 };

export function formatMoney(amountMinor: number, currency: string): string {
  const digits = MINOR_UNITS[currency] ?? 2;
  const major = amountMinor / 10 ** digits;
  return `${major.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits })} ${currency}`;
}

/** "in 12 min", "3 min ago", "in 2 h 5 min". */
export function relativeMinutes(iso: string, now: number = Date.now()): string {
  const minutes = Math.round((Date.parse(iso) - now) / 60_000);
  const span = Math.abs(minutes);
  const text = span >= 60 ? `${Math.floor(span / 60)} h${span % 60 ? ` ${span % 60} min` : ""}` : `${span} min`;
  return minutes >= 0 ? `in ${text}` : `${text} ago`;
}

export const QUEUE_LABELS: Record<string, string> = {
  security: "Security",
  triage: "Triage",
  cards: "Cards",
  topups: "Top-ups",
  transfers: "Transfers",
  exchange: "Exchange",
  fees: "Fees",
  verification: "Verification",
  account: "Account",
  general: "General",
};
