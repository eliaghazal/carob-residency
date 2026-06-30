import { type FormEvent, useEffect, useState } from "react";
import { api, ApiError, type Conversation as ConversationT, type Customer, type Message, type Staff } from "../api";
import { SlaTimer } from "../components/SlaTimer";
import { QUEUE_LABELS } from "../format";
import { CustomerPanel } from "./CustomerPanel";

type Loaded = { conversation: ConversationT; customer: Customer; messages: Message[] };

export function Conversation({ id, me, onBack }: { id: string; me: Staff; onBack: () => void }) {
  const [data, setData] = useState<Loaded | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () => api.conversation(id).then(setData).catch(() => setError("Could not load this conversation."));
  useEffect(() => {
    load();
  }, [id]); // load reads only `id`

  async function act(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  async function send(event: FormEvent) {
    event.preventDefault();
    if (!draft.trim()) return;
    await act(async () => {
      await api.reply(id, draft);
      setDraft("");
    });
  }

  if (!data) return error ? <p className="error">{error}</p> : <p className="muted">Loading</p>;
  const { conversation: c, customer, messages } = data;
  const mine = c.assigned_to === me.id;
  return (
    <div className="conversation">
      <header>
        <button className="link" onClick={onBack}>Back to queue</button>
        <h2>{customer.full_name}</h2>
        <p className="row muted">
          <span>{QUEUE_LABELS[c.queue] ?? c.queue}</span>
          <SlaTimer dueAt={c.sla_due_at} answered={c.first_response_at !== null} />
        </p>
        <div className="actions">
          {!mine && c.status !== "closed" ? <button disabled={busy} onClick={() => act(() => api.assignToMe(id))}>Assign to me</button> : null}
          {c.status !== "closed" ? <button disabled={busy} onClick={() => act(() => api.close(id))}>Close</button> : null}
        </div>
      </header>
      <ol className="messages">
        {messages.map((m) => (
          <li key={m.id} className={`message ${m.author_type}`} dir="auto">
            <span className="muted">{m.author_type === "staff" ? "Carob" : customer.full_name} · {new Date(m.created_at).toLocaleTimeString()}</span>
            <p>{m.body}</p>
          </li>
        ))}
      </ol>
      {c.status !== "closed" ? (
        <form onSubmit={send} className="reply">
          <label htmlFor="reply">Reply</label>
          <textarea id="reply" dir="auto" value={draft} onChange={(e) => setDraft(e.target.value)} rows={3} />
          <button type="submit" disabled={busy || !draft.trim()}>Send</button>
        </form>
      ) : (
        <p className="muted">This conversation is closed.</p>
      )}
      {error ? <p role="alert" className="error">{error}</p> : null}
      {mine || me.role !== "agent" ? <CustomerPanel customerId={customer.id} /> : <p className="muted">Assign the conversation to yourself to see the customer's wallets.</p>}
    </div>
  );
}
