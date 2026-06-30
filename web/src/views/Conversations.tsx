import { useEffect, useState } from "react";
import { api, type ConversationItem } from "../api";
import { SlaTimer } from "../components/SlaTimer";
import { QUEUE_LABELS } from "../format";

export function Conversations({ queue, onOpen }: { queue: string | null; onOpen: (id: string) => void }) {
  const [items, setItems] = useState<ConversationItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setItems(null);
    api
      .conversations(queue)
      .then((rows) => live && setItems(rows))
      .catch(() => live && setError("Could not load conversations."));
    return () => {
      live = false;
    };
  }, [queue]);

  if (error) return <p className="error">{error}</p>;
  if (!items) return <p className="muted">Loading conversations</p>;
  if (items.length === 0) return <p className="muted">No open conversations in {queue ? QUEUE_LABELS[queue] : "any queue"}.</p>;
  return (
    <ul className="conversations">
      {items.map(({ conversation: c, customer_name, last_message }) => (
        <li key={c.id}>
          <button onClick={() => onOpen(c.id)}>
            <span className="row">
              <strong>{customer_name}</strong>
              <SlaTimer dueAt={c.sla_due_at} answered={c.first_response_at !== null} />
            </span>
            <span className="row muted">
              <span>{QUEUE_LABELS[c.queue] ?? c.queue}</span>
              {c.intent ? <span>{c.intent.replaceAll("_", " ")}</span> : null}
            </span>
            <span className="preview">{last_message}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
