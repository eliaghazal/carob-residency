// A thin client for the staff API. Every call carries the signed staff token.

export type Staff = { id: string; email: string; name: string; role: "agent" | "supervisor" | "admin" };
export type QueueCount = { queue: string; waiting: number; breaching: number };
export type Conversation = {
  id: string;
  customer_id: string;
  status: "open" | "pending" | "closed";
  queue: string;
  intent: string | null;
  confidence: number | null;
  language: string | null;
  assigned_to: string | null;
  sla_due_at: string;
  first_response_at: string | null;
  created_at: string;
};
export type ConversationItem = { conversation: Conversation; customer_name: string; last_message: string | null };
export type Message = { id: number; author_type: "customer" | "staff" | "system"; body: string; created_at: string };
export type Customer = {
  id: string;
  full_name: string;
  email: string;
  phone: string | null;
  kyc_status: string;
  segment: string;
  locale: string;
  created_at: string;
};
export type Wallet = { id: string; currency: string; balance_minor: number; status: string };
export type Posting = { id: number; entry_id: string; account_id: string; amount_minor: number; currency: string; created_at: string };

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

const BASE = "/api";
const TOKEN_KEY = "carob.staff.token";

export const session = {
  token: (): string | null => sessionStorage.getItem(TOKEN_KEY),
  save: (token: string) => sessionStorage.setItem(TOKEN_KEY, token),
  clear: () => sessionStorage.removeItem(TOKEN_KEY),
};

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = session.token();
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(token ? { authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    if (response.status === 401) session.clear();
    throw new ApiError(response.status, body?.error?.code ?? "error", body?.error?.message ?? response.statusText);
  }
  return (await response.json()) as T;
}

export const api = {
  login: (email: string, password: string) =>
    call<{ token: string; staff: Staff }>("/staff/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  me: () => call<Staff>("/staff/me"),
  queues: () => call<QueueCount[]>("/staff/queues"),
  conversations: (queue: string | null, status = "open") =>
    call<ConversationItem[]>(`/staff/conversations?status=${status}${queue ? `&queue=${encodeURIComponent(queue)}` : ""}`),
  conversation: (id: string) =>
    call<{ conversation: Conversation; customer: Customer; messages: Message[] }>(`/staff/conversations/${id}`),
  reply: (id: string, body: string) =>
    call<Message>(`/staff/conversations/${id}/reply`, { method: "POST", body: JSON.stringify({ body }) }),
  assignToMe: (id: string) => call<Conversation>(`/staff/conversations/${id}/assign`, { method: "POST", body: "{}" }),
  close: (id: string) => call<Conversation>(`/staff/conversations/${id}/close`, { method: "POST" }),
  customer: (id: string) => call<{ customer: Customer; wallets: Wallet[]; recent: Posting[] }>(`/staff/customers/${id}`),
};
