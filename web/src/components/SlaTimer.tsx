import { useEffect, useState } from "react";
import { relativeMinutes } from "../format";

/** Time left before the first answer is due; red once breached. */
export function SlaTimer({ dueAt, answered }: { dueAt: string; answered: boolean }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(id);
  }, []);
  if (answered) return <span className="sla sla-ok">answered</span>;
  const breached = Date.parse(dueAt) < now;
  return (
    <span className={breached ? "sla sla-breached" : "sla"} title={new Date(dueAt).toLocaleString()}>
      {breached ? `breached ${relativeMinutes(dueAt, now)}` : `due ${relativeMinutes(dueAt, now)}`}
    </span>
  );
}
