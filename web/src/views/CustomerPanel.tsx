import { useEffect, useState } from "react";
import { api, type Customer, type Posting, type Wallet } from "../api";
import { formatMoney } from "../format";

export function CustomerPanel({ customerId }: { customerId: string }) {
  const [data, setData] = useState<{ customer: Customer; wallets: Wallet[]; recent: Posting[] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.customer(customerId).then(setData).catch((e) => setError(e.message ?? "Could not load the customer."));
  }, [customerId]);

  if (error) return <p className="muted">{error}</p>;
  if (!data) return <p className="muted">Loading customer</p>;
  return (
    <section className="customer" aria-label="Customer">
      <h3>Customer</h3>
      <p>
        {data.customer.email} · KYC {data.customer.kyc_status}
        {data.customer.segment === "vip" ? " · VIP" : ""}
      </p>
      <ul className="wallets">
        {data.wallets.map((w) => (
          <li key={w.id}>
            <span>{w.currency}</span>
            <strong>{formatMoney(w.balance_minor, w.currency)}</strong>
          </li>
        ))}
      </ul>
      <h4>Recent activity</h4>
      <table>
        <tbody>
          {data.recent.map((p) => (
            <tr key={p.id}>
              <td>{new Date(p.created_at).toLocaleString()}</td>
              <td className={p.amount_minor < 0 ? "debit" : "credit"}>{formatMoney(p.amount_minor, p.currency)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
