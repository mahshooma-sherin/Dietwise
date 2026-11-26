import type { Nutrition, Plan } from "../types";

const ROWS: { key: keyof Nutrition; label: string; unit: string }[] = [
  { key: "kcal", label: "Calories", unit: "kcal" },
  { key: "protein", label: "Protein", unit: "g" },
  { key: "carbs", label: "Carbohydrates", unit: "g" },
  { key: "fat", label: "Fat", unit: "g" },
  { key: "fiber", label: "Fiber", unit: "g" },
];
const GOAL: Record<string, string> = { balanced: "balanced nutrition", high_protein: "higher protein", high_fiber: "higher fiber", weight_management: "weight management" };

export default function NutritionPanel({ plan }: { plan: Plan }) {
  const n = plan.summary.nutrition;
  const sym = plan.currency.symbol;
  const s = plan.summary;
  return (
    <div className="nutrition">
      <div className="stats">
        <div><span className="muted">Shopping bill</span><strong>{sym}{s.grocery_total.toFixed(2)}</strong></div>
        <div><span className="muted">Cost of meals eaten</span><strong>{sym}{s.meals_cost.toFixed(2)}</strong></div>
        <div><span className="muted">Average per serving</span><strong>{sym}{s.avg_cost_per_serving.toFixed(2)}</strong></div>
        <div><span className="muted">Per day (average)</span><strong>{sym}{(s.meals_cost / plan.request.days).toFixed(2)}</strong></div>
      </div>
      <p className="muted small-print">The bill is higher than the cost of meals eaten when packs are bigger than what the plan uses.</p>

      <h3>Average per person per day, compared with a reference for {GOAL[plan.request.nutrition_goal]}</h3>
      <table>
        <thead><tr><th scope="col">Nutrient</th><th scope="col">Plan</th><th scope="col">Reference</th><th scope="col">Match</th></tr></thead>
        <tbody>
          {ROWS.map((r) => {
            const pct = n.percent_of_reference[r.key];
            return (
              <tr key={r.key}>
                <th scope="row">{r.label}</th>
                <td>{n.avg_per_person_day[r.key]} {r.unit}</td>
                <td>{n.reference_targets[r.key]} {r.unit}</td>
                <td>
                  <div className="bar" role="img" aria-label={`${pct ?? 0} percent of reference`}><i style={{ width: `${Math.min(100, pct ?? 0)}%` }} /></div>
                  <span>{pct ?? "-"}%</span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <h3>Day by day</h3>
      <div className="table-scroll">
        <table>
          <thead><tr><th scope="col">Day</th><th scope="col">kcal</th><th scope="col">Protein g</th><th scope="col">Fiber g</th><th scope="col">Cost</th></tr></thead>
          <tbody>
            {plan.days.map((d) => (
              <tr key={d.day}>
                <th scope="row">{d.day}</th><td>{Math.round(d.totals.nutrition.kcal)}</td><td>{Math.round(d.totals.nutrition.protein)}</td>
                <td>{Math.round(d.totals.nutrition.fiber)}</td><td>{sym}{d.totals.cost.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {n.meals_missing_nutrition_data > 0 && <div className="banner info">{n.meals_missing_nutrition_data} meals have incomplete nutrition data and are left out of these totals.</div>}
      <p className="muted small-print">{n.note}</p>
    </div>
  );
}
