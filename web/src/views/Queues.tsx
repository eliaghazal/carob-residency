import { useEffect, useState } from "react";
import { api, type QueueCount } from "../api";
import { QUEUE_LABELS } from "../format";

export function Queues({ selected, onSelect }: { selected: string | null; onSelect: (queue: string | null) => void }) {
  const [queues, setQueues] = useState<QueueCount[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    const load = () =>
      api
        .queues()
        .then((q) => live && (setQueues(q), setError(null)))
        .catch(() => live && setError("Queues are unavailable. Retrying."));
    load();
    return () => {
      live = false;
    };
  }, []);

  if (error && !queues) return <p className="muted">{error}</p>;
  if (!queues) return <p className="muted">Loading queues</p>;
  const total = queues.reduce((n, q) => n + q.waiting, 0);
  return (
    <nav aria-label="Queues" className="queues">
      <button className={selected === null ? "queue active" : "queue"} onClick={() => onSelect(null)}>
        <span>All queues</span>
        <span className="count">{total}</span>
      </button>
      {queues.map((q) => (
        <button key={q.queue} className={selected === q.queue ? "queue active" : "queue"} onClick={() => onSelect(q.queue)}>
          <span>{QUEUE_LABELS[q.queue] ?? q.queue}</span>
          <span className={q.breaching ? "count breaching" : "count"} title={`${q.breaching} past their SLA`}>
            {q.waiting}
          </span>
        </button>
      ))}
      {queues.length === 0 ? <p className="muted">Nobody is waiting.</p> : null}
    </nav>
  );
}
