import { useState } from "react";
import type { Plan, Rating } from "../types";
import MealPlan from "./MealPlan";
import ShoppingList from "./ShoppingList";
import NutritionPanel from "./NutritionPanel";

type Tab = "meals" | "shopping" | "nutrition";

interface Props {
  plan: Plan;
  ratings: Record<string, Rating>;
  onRate: (planId: string, recipeId: string, rating: Rating) => void;
  onNew: () => void;
}

export default function PlanView({ plan, ratings, onRate, onNew }: Props) {
  const [tab, setTab] = useState<Tab>("meals");
  const s = plan.summary;
  const sym = plan.currency.symbol;
  const over = plan.status === "over_budget";

  return (
    <section>
      <div className="plan-head">
        <div>
          <h2>{plan.request.days}-day plan for {plan.request.people} {plan.request.people === 1 ? "person" : "people"}</h2>
          <p className="muted">
            {s.distinct_dishes} different dishes across {s.total_meals} meals
            {s.cuisine_match_pct !== null ? ` · ${s.cuisine_match_pct}% from your preferred cuisine` : ""}
          </p>
        </div>
        <div className={`budget-card ${over ? "over" : ""}`} role="status">
          <span className="muted">Shopping bill</span>
          <strong>{sym}{s.grocery_total.toFixed(2)}</strong>
          <span>{over ? `over your ${sym}${s.budget} budget` : `${s.budget_used_pct}% of your ${sym}${s.budget} budget`}</span>
          <div className="meter" aria-hidden="true"><i style={{ width: `${Math.min(100, s.budget_used_pct)}%` }} /></div>
        </div>
      </div>

      {over && (
        <div className="banner warn" role="alert">
          <strong>{plan.warnings[0]}</strong>
          <p>What you can do:</p>
          <ul>{plan.suggestions.map((x) => <li key={x}>{x}</li>)}</ul>
        </div>
      )}
      {plan.warnings.slice(over ? 1 : 0).map((w) => <div className="banner info" key={w}>{w}</div>)}

      <div className="tabs" role="tablist" aria-label="Plan sections">
        {(["meals", "shopping", "nutrition"] as Tab[]).map((t) => (
          <button key={t} role="tab" id={`tab-${t}`} aria-selected={tab === t} aria-controls={`panel-${t}`} onClick={() => setTab(t)}>
            {t === "meals" ? "Daily meals" : t === "shopping" ? "Shopping list" : "Nutrition and cost"}
          </button>
        ))}
        <button className="btn small" onClick={onNew}>New plan</button>
      </div>

      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === "meals" && <MealPlan plan={plan} ratings={ratings} onRate={onRate} />}
        {tab === "shopping" && <ShoppingList plan={plan} />}
        {tab === "nutrition" && <NutritionPanel plan={plan} />}
      </div>

      <details className="notes">
        <summary>Notes and limits of this plan</summary>
        <ul>{plan.notes.map((n) => <li key={n}>{n}</li>)}</ul>
      </details>
    </section>
  );
}
