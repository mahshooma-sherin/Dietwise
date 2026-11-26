import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api";
import type { Meal, Plan, RecipeDetail } from "../types";

export default function RecipeModal({ meal, plan, onClose }: { meal: Meal; plan: Plan; onClose: () => void }) {
  const [servings, setServings] = useState(meal.servings);
  const [data, setData] = useState<RecipeDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    let live = true;
    setError(null);
    api.recipe(meal.recipe_id, servings, plan.currency.code, plan.request.price_level)
      .then((d) => live && setData(d))
      .catch((e: ApiError) => live && setError(e.message));
    return () => { live = false; };
  }, [meal.recipe_id, servings, plan.currency.code, plan.request.price_level]);

  const sym = plan.currency.symbol;
  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="recipe-title" onClick={(e) => e.stopPropagation()}>
        <button ref={closeRef} className="close" onClick={onClose} aria-label="Close recipe">Close</button>
        <h3 id="recipe-title">{meal.name}</h3>
        <p className="muted">{meal.description}</p>
        {error && <div className="banner error" role="alert">{error}</div>}
        {!data && !error && <p className="muted">Loading recipe…</p>}
        {data && (
          <>
            <label className="servings">Servings
              <input type="number" min={1} max={200} value={servings} onChange={(e) => setServings(Math.min(200, Math.max(1, +e.target.value || 1)))} />
            </label>
            <p className="muted">{data.time_min} min · {sym}{data.estimated_cost.toFixed(2)} total ({sym}{data.cost_per_serving.toFixed(2)} per serving)
              {data.allergens.length ? ` · contains: ${data.allergens.join(", ")}` : ""}</p>
            <h4>Ingredients for {data.servings} {data.servings === 1 ? "serving" : "servings"}</h4>
            <ul className="ingredients">
              {data.ingredients.map((i) => <li key={i.id}><span>{i.name}</span><span>{i.display}</span></li>)}
            </ul>
            <h4>Method</h4>
            <ol>{data.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
            {data.nutrition_per_serving ? (
              <p className="muted">Per serving (estimate): {Math.round(data.nutrition_per_serving.kcal)} kcal · {data.nutrition_per_serving.protein} g protein · {data.nutrition_per_serving.carbs} g carbs · {data.nutrition_per_serving.fat} g fat · {data.nutrition_per_serving.fiber} g fiber</p>
            ) : <p className="muted">Nutrition data is incomplete for this dish.</p>}
            <p className="muted small-print">Source: {data.source}</p>
          </>
        )}
      </div>
    </div>
  );
}
