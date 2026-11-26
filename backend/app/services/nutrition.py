from __future__ import annotations

from .. import config
from ..data_loader import NUTRIENTS


def day_totals(meals) -> dict:
    """Per-person nutrition for one day (each person eats one serving of each meal)."""
    tot = dict.fromkeys(NUTRIENTS, 0.0)
    for m in meals:
        if m["nutrition"]:
            for n in NUTRIENTS:
                tot[n] += m["nutrition"][n]
    return {n: round(v, 1) for n, v in tot.items()}


def summarize(days, req) -> dict:
    slots = config.MEAL_SLOTS[req.meals_per_day]
    share = sum(config.SLOT_SHARE[s] for s in slots)
    base = config.REFERENCE_TARGETS[req.nutrition_goal]
    targets = {n: round(base[n] * share, 1) for n in NUTRIENTS}
    n_days = len(days)
    avg = {n: round(sum(d["totals"]["nutrition"][n] for d in days) / n_days, 1) for n in NUTRIENTS}
    pct = {n: round(100 * avg[n] / targets[n]) if targets[n] else None for n in NUTRIENTS}
    incomplete = sum(1 for d in days for m in d["meals"] if not m["nutrition"])
    return {"avg_per_person_day": avg, "reference_targets": targets, "percent_of_reference": pct,
            "meals_missing_nutrition_data": incomplete,
            "note": ("Reference values are generic, scaled to the meals you selected, and are not medical advice. "
                     "Estimates are computed from ingredient composition values and depend on brands, "
                     "preparation and portion sizes.")}
