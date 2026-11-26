import { useState } from "react";
import type { ApiError } from "../api";
import type { Meta, PlanRequest } from "../types";

const UNIT_G: Record<string, number> = { g: 1, kg: 1000, lb: 453.592, oz: 28.3495 };

function splitList(s: string): string[] {
  return s.split(/[,\n]/).map((x) => x.trim()).filter(Boolean);
}

// "rice 500g", "onions", "oil 1 kg" -> { name, grams? }. No amount means "I have plenty".
function parsePantry(s: string): { name: string; grams?: number }[] {
  return splitList(s).map((token) => {
    const m = token.match(/^(.*?)[\s:]+(\d+(?:\.\d+)?)\s*(kg|g|lb|oz)?$/i);
    if (!m) return { name: token };
    return { name: m[1].trim(), grams: parseFloat(m[2]) * UNIT_G[(m[3] ?? "g").toLowerCase()] };
  });
}

const EQUIP_LABEL: Record<string, string> = {
  stovetop: "Stovetop", oven: "Oven", pressure_cooker: "Pressure cooker", air_fryer: "Air fryer", microwave: "Microwave", blender: "Blender",
};

interface Props {
  meta: Meta;
  busy: boolean;
  error: ApiError | null;
  onSubmit: (r: PlanRequest) => void;
}

export default function PlanForm({ meta, busy, error, onSubmit }: Props) {
  const [budget, setBudget] = useState("60");
  const [currency, setCurrency] = useState("USD");
  const [pref, setPref] = useState<PlanRequest["food_preference"]>("non_vegetarian");
  const [goal, setGoal] = useState<PlanRequest["nutrition_goal"]>("balanced");
  const [days, setDays] = useState(5);
  const [people, setPeople] = useState(2);
  const [cuisine, setCuisine] = useState("any");
  const [meals, setMeals] = useState<2 | 3 | 4>(3);
  const [allergies, setAllergies] = useState("");
  const [dislikes, setDislikes] = useState("");
  const [pantry, setPantry] = useState("");
  const [cook, setCook] = useState<PlanRequest["max_cook_time"]>("long");
  const [equipment, setEquipment] = useState<string[]>(["stovetop"]);
  const [priceLevel, setPriceLevel] = useState("1");
  const [packs, setPacks] = useState(true);
  const [allowRepeats, setAllowRepeats] = useState(false);
  const [repeats, setRepeats] = useState(1);
  const [localErr, setLocalErr] = useState<string | null>(null);

  const onCurrency = (c: string) => {
    setCurrency(c);
    if (c === "INR" && priceLevel === "1") setPriceLevel("0.4");   // starter prices are USD-based; typical Indian grocery prices are lower
  };

  const symbol = meta.currencies.find((c) => c.code === currency)?.symbol ?? "";

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const b = parseFloat(budget);
    if (!Number.isFinite(b) || b <= 0) return setLocalErr("Enter a budget greater than zero.");
    setLocalErr(null);
    onSubmit({
      budget: b, currency, food_preference: pref, nutrition_goal: goal, days, people, cuisine, meals_per_day: meals,
      allergies: splitList(allergies), dislikes: splitList(dislikes), available_ingredients: parsePantry(pantry),
      max_cook_time: cook, equipment, price_level: parseFloat(priceLevel), round_to_packs: packs, max_repeats: repeats, allow_repeats_for_budget: allowRepeats,
    });
  };

  const toggleEquip = (e: string) => setEquipment((cur) => (cur.includes(e) ? cur.filter((x) => x !== e) : [...cur, e]));

  return (
    <form className="form" onSubmit={submit} noValidate>
      <h2>Build your meal plan</h2>

      <fieldset>
        <legend>The basics</legend>
        <div className="grid">
          <label>Total budget
            <div className="inline">
              <select aria-label="Currency" value={currency} onChange={(e) => onCurrency(e.target.value)}>
                {meta.currencies.map((c) => <option key={c.code} value={c.code}>{c.code}</option>)}
              </select>
              <input inputMode="decimal" value={budget} onChange={(e) => setBudget(e.target.value)} aria-describedby="budget-help" />
            </div>
            <small id="budget-help">For the whole period, in {symbol.trim() || currency}. This covers groceries you still need to buy.</small>
          </label>
          <label>Food preference
            <select value={pref} onChange={(e) => setPref(e.target.value as PlanRequest["food_preference"])}>
              <option value="non_vegetarian">Non-vegetarian</option>
              <option value="vegetarian">Vegetarian</option>
              <option value="vegan">Vegan</option>
            </select>
          </label>
          <label>Nutrition goal
            <select value={goal} onChange={(e) => setGoal(e.target.value as PlanRequest["nutrition_goal"])}>
              <option value="balanced">Balanced nutrition</option>
              <option value="high_protein">Higher protein</option>
              <option value="high_fiber">Higher fiber</option>
              <option value="weight_management">Weight management</option>
            </select>
          </label>
          <label>Days: <strong>{days}</strong>
            <input type="range" min={1} max={30} value={days} onChange={(e) => setDays(+e.target.value)} />
          </label>
          <label>People eating
            <input type="number" min={1} max={20} value={people} onChange={(e) => setPeople(Math.min(20, Math.max(1, +e.target.value || 1)))} />
          </label>
          <label>Meals per day
            <select value={meals} onChange={(e) => setMeals(+e.target.value as 2 | 3 | 4)}>
              <option value={2}>Two (lunch, dinner)</option>
              <option value={3}>Three (breakfast, lunch, dinner)</option>
              <option value={4}>Three plus a snack</option>
            </select>
          </label>
        </div>
      </fieldset>

      <fieldset>
        <legend>Tastes and restrictions</legend>
        <div className="grid">
          <label>Preferred cuisine
            <select value={cuisine} onChange={(e) => setCuisine(e.target.value)}>
              <option value="any">Any cuisine</option>
              {meta.cuisines.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
            </select>
          </label>
          <label>Cooking time
            <select value={cook} onChange={(e) => setCook(e.target.value as PlanRequest["max_cook_time"])}>
              <option value="quick">Quick (25 min or less)</option>
              <option value="moderate">Moderate (up to 45 min)</option>
              <option value="long">Any length</option>
            </select>
          </label>
          <label className="wide">Allergies and restrictions
            <input value={allergies} onChange={(e) => setAllergies(e.target.value)} placeholder="peanuts, shellfish, gluten, dairy" aria-describedby="allergy-help" />
            <small id="allergy-help">These dishes are removed before any ranking. Separate with commas. Terms we can't match are flagged.</small>
          </label>
          <label className="wide">Disliked foods
            <input value={dislikes} onChange={(e) => setDislikes(e.target.value)} placeholder="mushrooms, biryani" />
          </label>
          <label className="wide">Ingredients you already have
            <textarea rows={2} value={pantry} onChange={(e) => setPantry(e.target.value)} placeholder="rice 1kg, onions, cooking oil 500g" aria-describedby="pantry-help" />
            <small id="pantry-help">With an amount, we subtract it. Without one, we treat it as plenty at home.</small>
          </label>
        </div>
        <div className="checks" role="group" aria-label="Cooking equipment">
          <span className="checks-label">Equipment you have</span>
          {meta.equipment.map((e) => (
            <label key={e} className="check">
              <input type="checkbox" checked={equipment.includes(e)} onChange={() => toggleEquip(e)} /> {EQUIP_LABEL[e] ?? e}
            </label>
          ))}
        </div>
      </fieldset>

      <details className="advanced">
        <summary>Pricing and variety settings</summary>
        <div className="grid">
          <label>Local price level
            <select value={priceLevel} onChange={(e) => setPriceLevel(e.target.value)}>
              <option value="0.4">Low grocery prices (about 40%, e.g. India - rough estimate)</option>
              <option value="0.5">Low-cost region (half the starter prices)</option>
              <option value="1">Average (starter prices)</option>
              <option value="1.5">High-cost region (1.5 times)</option>
              <option value="2">Very high-cost (twice)</option>
            </select>
            <small>{meta.currency_note}</small>
          </label>
          <label>Most times one dish may repeat: <strong>{repeats}</strong>
            <input type="range" min={1} max={5} value={repeats} onChange={(e) => setRepeats(+e.target.value)} />
            <small>Repeats still happen if there aren't enough dishes or the budget needs them, and we tell you why.</small>
          </label>
          <label className="check wide">
            <input type="checkbox" checked={allowRepeats} onChange={(e) => setAllowRepeats(e.target.checked)} /> Allow repeated dishes to fit my budget (otherwise variety comes first and the plan may exceed a very tight budget)
          </label>
          <label className="check wide">
            <input type="checkbox" checked={packs} onChange={(e) => setPacks(e.target.checked)} /> Round the shopping list up to pack sizes
          </label>
        </div>
      </details>

      {(localErr || error) && (
        <div className="banner error" role="alert">
          <strong>{localErr ?? error?.message}</strong>
          {error?.details.length ? <ul>{error.details.map((d) => <li key={d}>{d}</li>)}</ul> : null}
        </div>
      )}

      <button className="btn primary big" type="submit" disabled={busy}>{busy ? "Planning your meals…" : "Create meal plan"}</button>
    </form>
  );
}
