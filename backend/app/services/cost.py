from __future__ import annotations


def build_price_table(store, currency, price_level, overrides, free_ids):
    """Local-currency price per kg for each ingredient. Pantry 'plenty' items cost 0."""
    fx = store.currencies[currency]["rate"]
    prices, missing = {}, []
    for ing in store.ingredients.values():
        if ing.id in overrides:
            p = float(overrides[ing.id])
        elif ing.price_usd_kg is None:
            p = 0.0
            missing.append(ing.id)
        else:
            p = ing.price_usd_kg * fx * price_level
        prices[ing.id] = 0.0 if ing.id in free_ids else p
    return prices, missing


def recipe_cost_per_serving(recipe, prices) -> float:
    return sum(g / 1000.0 * prices[i] for i, g in recipe.ingredients.items())
