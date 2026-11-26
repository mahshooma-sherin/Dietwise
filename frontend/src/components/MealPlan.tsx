import { useState } from "react";
import type { Meal, Plan, Rating } from "../types";
import RecipeModal from "./RecipeModal";

const SLOT_LABEL: Record<string, string> = { breakfast: "Breakfast", lunch: "Lunch", dinner: "Dinner", snack: "Snack" };
const RATINGS: { id: Rating; label: string }[] = [
  { id: "like", label: "Like" },
  { id: "dislike", label: "Dislike" },
  { id: "cook_again", label: "Cook again" },
];

interface Props {
  plan: Plan;
  ratings: Record<string, Rating>;
  onRate: (planId: string, recipeId: string, rating: Rating) => void;
}

export default function MealPlan({ plan, ratings, onRate }: Props) {
  const [open, setOpen] = useState<Meal | null>(null);
  const sym = plan.currency.symbol;

  return (
    <>
      <div className="days">
        {plan.days.map((d) => (
          <article className="day" key={d.day} aria-labelledby={`day-${d.day}`}>
            <header>
              <h3 id={`day-${d.day}`}>Day {d.day}</h3>
              <span className="muted">{Math.round(d.totals.nutrition.kcal)} kcal per person · {sym}{d.totals.cost.toFixed(2)}</span>
            </header>
            <ul>
              {d.meals.map((m) => (
                <li className="meal" key={m.slot}>
                  <div className="meal-slot">{SLOT_LABEL[m.slot]}</div>
                  <div className="meal-body">
                    <button className="meal-name" onClick={() => setOpen(m)}>{m.name}</button>
                    <p className="muted">{m.cuisine_label} · {m.time_min} min · {sym}{m.cost_per_serving.toFixed(2)} per serving
                      {m.nutrition ? ` · ${Math.round(m.nutrition.kcal)} kcal, ${Math.round(m.nutrition.protein)} g protein` : " · nutrition data incomplete"}</p>
                    {m.reasons.length > 0 && <p className="why">{m.reasons.join(" · ")}</p>}
                    <div className="rate" role="group" aria-label={`Rate ${m.name}`}>
                      {RATINGS.map((r) => (
                        <button key={r.id} aria-pressed={ratings[m.recipe_id] === r.id} onClick={() => { onRate(plan.id, m.recipe_id, r.id); if (r.id === "cook_again") setOpen(m); }}>
                          {r.label}
                        </button>
                      ))}
                    </div>
                    {ratings[m.recipe_id] === "dislike" && <p className="why">Noted: this dish won't be picked in new plans.</p>}
                    {ratings[m.recipe_id] === "cook_again" && <p className="why">Saved. Open the recipe any time with the dish name.</p>}
                  </div>
                </li>
              ))}
            </ul>
          </article>
        ))}
      </div>
      <p className="muted small-print">Ratings are saved and shape your next plans. A disliked dish won't be chosen again.</p>
      {open && <RecipeModal meal={open} plan={plan} onClose={() => setOpen(null)} />}
    </>
  );
}
