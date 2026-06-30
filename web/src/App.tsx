import { useEffect, useState } from "react";
import { api, session, type Staff } from "./api";
import { Conversation } from "./views/Conversation";
import { Conversations } from "./views/Conversations";
import { Login } from "./views/Login";
import { Queues } from "./views/Queues";

// Routes live in the hash so the console works behind any static file server:
// #/queue/cards, #/conversation/<id>
function parse(hash: string): { queue: string | null; conversation: string | null } {
  const [, kind, value] = hash.replace(/^#/, "").split("/");
  return { queue: kind === "queue" ? value ?? null : null, conversation: kind === "conversation" ? value ?? null : null };
}

export function App() {
  const [me, setMe] = useState<Staff | null>(null);
  const [checking, setChecking] = useState(Boolean(session.token()));
  const [route, setRoute] = useState(() => parse(location.hash));

  useEffect(() => {
    const onHash = () => setRoute(parse(location.hash));
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    if (!session.token()) return;
    api
      .me()
      .then(setMe)
      .catch(() => session.clear())
      .finally(() => setChecking(false));
  }, []);

  if (checking) return <p className="muted center">Loading</p>;
  if (!me) return <Login onLogin={setMe} />;

  const go = (hash: string) => (location.hash = hash);
  return (
    <div className="shell">
      <header className="top">
        <strong>Carob console</strong>
        <span className="muted">
          {me.name} · {me.role}
        </span>
        <button
          className="link"
          onClick={() => {
            session.clear();
            setMe(null);
          }}
        >
          Sign out
        </button>
      </header>
      <aside>
        <Queues selected={route.queue} onSelect={(q) => go(q ? `#/queue/${q}` : "#/")} />
      </aside>
      <main>
        {route.conversation ? (
          <Conversation id={route.conversation} me={me} onBack={() => history.back()} />
        ) : (
          <Conversations queue={route.queue} onOpen={(id) => go(`#/conversation/${id}`)} />
        )}
      </main>
    </div>
  );
}
