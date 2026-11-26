import { useEffect, useState } from "react";
import { api } from "../api";
import type { Plan } from "../types";

export default function ShoppingList({ plan }: { plan: Plan }) {
  const key = `dietwise:checked:${plan.id}`;
  const [done, setDone] = useState<Record<string, boolean>>({});
  const sym = plan.currency.symbol;

  useEffect(() => {
    try { setDone(JSON.parse(localStorage.getItem(key) ?? "{}")); } catch { setDone({}); }
  }, [key]);

  const toggle = (id: string) => {
    const next = { ...done, [id]: !done[id] };
    setDone(next);
    try { localStorage.setItem(key, JSON.stringify(next)); } catch { /* storage unavailable */ }
  };

  const items = plan.shopping_list.groups.flatMap((g) => g.items);
  const toBuy = items.filter((i) => i.purchase_g > 0);
  const remaining = toBuy.filter((i) => !done[i.id]).reduce((s, i) => s + i.estimated_cost, 0);

  return (
    <div className="receipt-wrap">
      <div className="receipt" aria-label="Shopping list">
        <header>
          <h3>Shopping list</h3>
          <p className="muted">{plan.request.days} days · {plan.request.people} {plan.request.people === 1 ? "person" : "people"} · {toBuy.length} items to buy</p>
        </header>
        {plan.shopping_list.groups.map((g) => (
          <section key={g.category} aria-labelledby={`cat-${g.category}`}>
            <h4 id={`cat-${g.category}`}>{g.category}</h4>
            <ul>
              {g.items.map((i) => {
                const have = i.purchase_g === 0;
                return (
                  <li key={i.id} className={done[i.id] || have ? "done" : ""}>
                    <label>
                      <input type="checkbox" checked={!!done[i.id] || have} disabled={have} onChange={() => toggle(i.id)} />
                      <span className="item-name">{i.name}</span>
                      <span className="leader" aria-hidden="true" />
                      <span className="item-qty">{i.purchase_display}</span>
                      <span className="item-cost">{have ? "" : `${sym}${i.estimated_cost.toFixed(2)}`}</span>
                    </label>
                    <small className="muted">
                      Needed {i.needed_display}
                      {i.available_unlimited ? "; you have plenty" : i.available_g ? `; you have ${Math.round(i.available_g)} g` : ""}
                      {i.purchase_g > i.to_buy_g + 0.5 ? `; rounded up to a pack from ${Math.round(i.to_buy_g)} g` : ""}
                    </small>
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
        <footer>
          <div className="total"><span>Estimated total</span><strong>{sym}{plan.shopping_list.total_cost.toFixed(2)}</strong></div>
          <div className="total sub"><span>Still to buy</span><span>{sym}{remaining.toFixed(2)}</span></div>
        </footer>
      </div>
      <div className="receipt-actions">
        <a className="btn" href={api.csvUrl(plan.id)} download>Download CSV</a>
        <button className="btn" onClick={() => window.print()}>Print</button>
        <p className="muted small-print">Estimates use the starter price dataset, not live shop prices. Adjust the local price level when creating a plan.</p>
      </div>
    </div>
  );
}
