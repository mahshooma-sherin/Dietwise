from __future__ import annotations

from ..data_loader import CUISINE_LABELS, NUTRIENTS
from ..units import format_qty
from .cost import build_price_table


def recipe_detail(store, recipe_id: str, servings: int, currency: str = "USD", price_level: float = 1.0) -> dict:
    r = store.recipe_by_id[recipe_id]
    prices, _ = build_price_table(store, currency, price_level, {}, set())
    items, cost = [], 0.0
    for iid, g in r.ingredients.items():
        ing = store.ingredients[iid]
        total = g * servings
        c = total / 1000.0 * prices[iid]
        cost += c
        items.append({"id": iid, "name": ing.name, "category": ing.category, "grams_per_serving": g,
                      "grams_total": round(total, 2), "display": format_qty(total, ing.piece_g),
                      "estimated_cost": round(c, 2)})
    n = r.nutrition
    return {
        "id": r.id, "name": r.name, "cuisine": r.cuisine, "cuisine_label": CUISINE_LABELS.get(r.cuisine, r.cuisine),
        "description": r.description, "meals": r.meals, "time_min": r.time_min, "equipment": r.equipment,
        "diet": r.diet, "allergens": sorted(r.allergens), "servings": servings, "ingredients": items,
        "steps": r.steps, "source": r.source, "currency": {"code": currency, "symbol": store.currencies[currency]["symbol"]},
        "estimated_cost": round(cost, 2), "cost_per_serving": round(cost / servings, 2),
        "nutrition_per_serving": n,
        "nutrition_total": {k: round(v * servings, 1) for k, v in n.items()} if n else None,
    }
