"""Orchestrates: validate -> filter -> rank (ML) -> MMR variety -> optimize -> arrange -> grocery -> summary."""
from __future__ import annotations

import math
import random
import uuid
from datetime import datetime, timezone

import numpy as np

from .. import config
from ..data_loader import CUISINE_LABELS, get_store
from ..ml.diversity import mmr
from ..ml.recommender import get_recommender
from ..optimization.optimizer import solve_counts
from .cost import build_price_table, recipe_cost_per_serving
from .filters import assert_plan_safe, filter_recipes
from .grocery import build_shopping_list
from .nutrition import day_totals, summarize
from .validation import validate_request

DISCLAIMERS = [
    "Prices are indicative estimates from data/ingredients.csv (scaled by currency and price level), not live market prices.",
    "Nutrition is calculated from approximate ingredient composition values; it is not medical advice and does not promise any health outcome.",
]


class PlanInputError(Exception):
    def __init__(self, errors):
        self.errors = errors
        super().__init__("; ".join(errors))


def _slots(req) -> dict:
    by_type = {"breakfast": [], "main": [], "snack": []}
    for d in range(req.days):
        for slot in config.MEAL_SLOTS[req.meals_per_day]:
            by_type[config.SLOT_TYPE[slot]].append((d, slot))
    return {t: v for t, v in by_type.items() if v}


def arrange(counts: dict, rng: random.Random) -> list:
    """Order dishes so repeats are spread out: a dish is not reused until as many other dishes as possible
    have been served (round-robin with a cooldown). This also stops the same dish landing in the same slot
    on consecutive days."""
    remaining = dict(counts)
    items = list(remaining)
    rng.shuffle(items)
    out: list = []
    cooldown = max(0, len(items) - 1)
    for _ in range(sum(counts.values())):
        g = cooldown
        while True:
            recent = set(out[-g:]) if g > 0 else set()
            avail = [r for r in items if remaining[r] > 0 and r not in recent]
            if avail or g == 0:
                break
            g -= 1
        pick = max(avail, key=lambda r: remaining[r])
        out.append(pick)
        remaining[pick] -= 1
    return out


def smooth(seq: list, rec, rng: random.Random, iters: int = 400) -> list:
    """Hill-climb by swapping meals so that neighbouring meals are as different as possible
    (same-day lunch/dinner and day-to-day neighbours). Dish counts never change."""
    if len(seq) < 3:
        return seq
    idx = rec.idx

    def cost(s):
        return sum(rec.sim[idx[a], idx[b]] for a, b in zip(s, s[1:]))

    best, best_c = list(seq), cost(seq)
    for _ in range(iters):
        i, j = rng.sample(range(len(best)), 2)
        if best[i] == best[j]:
            continue
        cand = best[:]
        cand[i], cand[j] = cand[j], cand[i]
        if any(a == b for a, b in zip(cand, cand[1:])):
            continue
        c = cost(cand)
        if c < best_c - 1e-12:
            best, best_c = cand, c
    return best


def generate_plan(req, store=None, rec=None, feedback=None) -> dict:
    store = store or get_store()
    rec = rec or get_recommender(store)
    feedback = feedback or {}
    errors, warnings, pantry = validate_request(req, store)
    if errors:
        raise PlanInputError(errors)

    cur = store.currencies[req.currency]
    sym = cur["symbol"]
    P = req.people
    free_ids = {i for i, g in pantry.items() if math.isinf(g)}
    prices, missing_prices = build_price_table(store, req.currency, req.price_level, req.price_overrides, free_ids)
    slots = _slots(req)

    # 1. Hard filters (diet, allergies, dislikes, equipment, time, previously disliked dishes)
    excluded = {rid for rid, rt in feedback.items() if rt == "dislike"}
    eligible, stats = filter_recipes(store, req, excluded, apply_time=True)
    eligible_relaxed, _ = filter_recipes(store, req, excluded, apply_time=False)
    elig_by_type = {}
    for t, sl in slots.items():
        e = [r for r in eligible if t in r.meals]
        if len(e) < min(len(sl), 3):
            e2 = [r for r in eligible_relaxed if t in r.meals]
            if len(e2) > len(e):
                warnings.append(f"Few {t} dishes fit your cooking-time limit, so longer recipes were allowed for {t} meals.")
                e = e2
        if not e:
            raise PlanInputError([
                f"No {t} recipes match your diet, allergies, dislikes and equipment. "
                f"Try removing a dislike, adding cooking equipment or changing the food preference. "
                f"(Filtered out: {dict(stats)})"])
        elig_by_type[t] = e
        if len(e) < len(sl):
            label = "lunch/dinner" if t == "main" else t
            warnings.append(f"Only {len(e)} {label} dishes match your settings but your plan has {len(sl)} {label} meals, "
                            f"so at least {len(sl) - len(e)} repeat. Relax a filter or add recipes to data/recipes.json for more variety.")

    # 2. ML ranking
    candidates = list({r.id: r for t in elig_by_type for r in elig_by_type[t]}.values())
    cost_ps = {r.id: recipe_cost_per_serving(r, prices) for r in candidates}
    scores = rec.score(candidates, req, feedback, cost_ps, set(pantry))
    rng = random.Random(req.seed)  # seeded => reproducible; seed=None => a different plan each time
    for r in sorted(candidates, key=lambda x: x.id):
        scores[r.id]["score"] += rng.uniform(0.0, config.RANDOMNESS)

    # 3. Variety: MMR candidate pool per meal type
    pools, caps = {}, {}
    for t, sl in slots.items():
        e = elig_by_type[t]
        rel = np.array([scores[r.id]["score"] for r in e])
        k = min(len(e), max(12, 3 * len(sl)))
        pools[t] = [e[i] for i in mmr(rel, rec.similarity(e), k, config.MMR_LAMBDA)]
        caps[t] = max(req.max_repeats, math.ceil(len(sl) / len(pools[t])))

    cost_plan = {r.id: cost_ps[r.id] * P for t in pools for r in pools[t]}
    ref = float(np.mean(list(cost_plan.values()))) or 1.0
    finite_have = {i: g for i, g in pantry.items() if not math.isinf(g)}

    def make_spec(cap_map):
        return {"types": {t: {"slots": len(slots[t]), "pool": [r.id for r in pools[t]], "cap": cap_map[t]} for t in slots},
                "score": {r.id: scores[r.id]["score"] for t in pools for r in pools[t]},
                "ingredients": {r.id: dict(r.ingredients) for t in pools for r in pools[t]},
                "people": P, "pack": {i.id: (i.pack_g if req.round_to_packs else 1.0) for i in store.ingredients.values()},
                "price": prices, "have": finite_have, "free": free_ids, "round": req.round_to_packs, "ref": ref}

    def shopping_for(counts):
        meals = [(store.recipe_by_id[rid], P * c) for t in counts for rid, c in counts[t].items()]
        return build_shopping_list(store, meals, pantry, prices, req.round_to_packs)

    # 4. Budget feasibility: cheapest plan first (normal variety, then allowing repeats)
    relaxed_caps = {t: min(len(slots[t]), max(caps[t], 6)) for t in slots}
    chosen_caps, counts, shop, solver_note = None, None, None, "optimal"
    cheapest = None
    for cap_map in ((caps, relaxed_caps) if req.allow_repeats_for_budget else (caps,)):
        spec = make_spec(cap_map)
        cmin = solve_counts(spec, None, "min_cost")
        if cmin is None:
            continue
        smin = shopping_for(cmin)
        if cheapest is None or smin["total_cost"] < cheapest[2]["total_cost"]:
            cheapest = (cap_map, cmin, smin)
        if smin["total_cost"] <= req.budget + 1e-9:
            chosen_caps = cap_map
            if cap_map is relaxed_caps and cap_map != caps:
                warnings.append("To fit your budget some dishes repeat more often than your variety setting allows (you allowed this).")
            # 5. Quality-maximising solve under the budget; tighten if pack rounding pushes the real bill over
            b_eff, counts, shop = req.budget, cmin, smin
            for _ in range(6):
                cand = solve_counts(spec, b_eff, "balanced")
                if cand is None:
                    break
                s = shopping_for(cand)
                if s["total_cost"] <= req.budget + 1e-9:
                    counts, shop = cand, s
                    break
                b_eff -= (s["total_cost"] - req.budget) * 1.05 + 1e-6
                if b_eff <= 0:
                    break
            break

    status, suggestions = "ok", []
    if counts is None:
        if cheapest is None:
            raise PlanInputError(["The optimizer could not build any plan with these settings."])
        chosen_caps, counts, shop = cheapest
        status = "over_budget"
        need = shop["total_cost"]
        warnings.insert(0, f"Your budget of {sym}{req.budget:,.2f} is too low for this plan. The cheapest varied plan we "
                           f"could build costs about {sym}{need:,.2f}; it is shown below, over budget.")
        suggestions = [f"Raise the budget to at least {sym}{math.ceil(need):,}.",
                       "Lower the local price level if groceries in your area cost less than the starter prices.",
                       "Turn off 'Round up to pack sizes' to buy loose quantities.",
                       "Plan fewer days or feed fewer people.",
                       "Plan fewer meals per day (drop the snack or breakfast).",
                       "Add pantry ingredients you already own."]
        if not req.allow_repeats_for_budget:
            suggestions.insert(1, "Tick 'Allow repeated dishes to fit my budget' to get a cheaper plan that repeats some meals.")
        if req.max_cook_time != "long":
            suggestions.append("Allow longer cooking times to widen the choice of cheap dishes.")
        if req.cuisine != "any":
            suggestions.append("Choose 'any cuisine' so cheaper dishes from other cuisines can be used.")
        if req.dislikes or req.allergies:
            suggestions.append("Remove optional dislikes to widen the choice (never remove real allergies).")

    # 6. Arrange dishes across days and assemble the plan
    by_day = {d: [] for d in range(req.days)}
    used = []
    for t, sl in slots.items():
        seq = smooth(arrange(counts[t], rng), rec, rng)
        for (d, slot), rid in zip(sl, seq):
            r = store.recipe_by_id[rid]
            used.append(r)
            sc = scores.get(rid, {"score": 0.0, "reasons": []})
            by_day[d].append({
                "slot": slot, "recipe_id": rid, "name": r.name, "cuisine": r.cuisine,
                "cuisine_label": CUISINE_LABELS.get(r.cuisine, r.cuisine), "description": r.description,
                "time_min": r.time_min, "servings": P, "cost_per_serving": round(cost_ps.get(rid, 0.0), 2),
                "cost": round(cost_ps.get(rid, 0.0) * P, 2), "nutrition": r.nutrition, "diet": r.diet,
                "allergens": sorted(r.allergens), "match_score": max(0, min(100, round(sc["score"] / 1.1 * 100))),
                "reasons": sc["reasons"],
            })
    order = config.MEAL_SLOTS[req.meals_per_day]
    days = []
    for d in range(req.days):
        meals = sorted(by_day[d], key=lambda m: order.index(m["slot"]))
        days.append({"day": d + 1, "meals": meals,
                     "totals": {"nutrition": day_totals(meals), "cost": round(sum(m["cost"] for m in meals), 2)}})
    assert_plan_safe(used, req, store)

    # 7. Notes and summary
    notes = list(DISCLAIMERS)
    for t, sl in slots.items():
        for rid, c in counts[t].items():
            if c > 1:
                why = (f"only {len(elig_by_type[t])} eligible {t} dishes fit your settings" if
                       len(elig_by_type[t]) * req.max_repeats < len(sl) else "your budget or variety setting required it")
                notes.append(f"'{store.recipe_by_id[rid].name}' appears {c} times because {why}.")
    used_missing = sorted({store.ingredients[i].name for r in used for i in r.ingredients if i in missing_prices})
    if used_missing:
        warnings.append("No price data for: " + ", ".join(used_missing) + ". These were counted as free.")
    if len({r.id for r in used}) < 0.5 * len(used) and len(used) >= 6:
        hints = ["raise the budget", "lower the local price level if prices in your area are cheaper than the starter data",
                 "turn off 'round up to pack sizes'", "plan fewer people or days"]
        warnings.append(f"Only {len({r.id for r in used})} different dishes fit this budget, so meals repeat. "
                        f"For more variety: {'; '.join(hints)}.")
    if status == "ok" and shop["total_cost"] > 0.95 * req.budget:
        warnings.append("This plan uses more than 95% of your budget; there is little room for price differences.")

    total_servings = req.days * len(config.MEAL_SLOTS[req.meals_per_day]) * P
    consumption = round(sum(m["cost"] for d in days for m in d["meals"]), 2)
    cuisine_match = None
    if req.cuisine != "any":
        cuisine_match = round(100 * sum(1 for r in used if r.cuisine == req.cuisine) / len(used))
    plan = {
        "id": uuid.uuid4().hex[:12], "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": status, "warnings": warnings, "suggestions": suggestions, "notes": notes,
        "currency": {"code": req.currency, "symbol": sym}, "request": req.model_dump(),
        "days": days, "shopping_list": shop,
        "summary": {
            "budget": req.budget, "grocery_total": shop["total_cost"],
            "budget_used_pct": round(100 * shop["total_cost"] / req.budget, 1),
            "meals_cost": consumption, "total_servings": total_servings,
            "avg_cost_per_serving": round(consumption / total_servings, 2),
            "distinct_dishes": len({r.id for r in used}), "total_meals": len(used),
            "cuisine_match_pct": cuisine_match,
            "nutrition": summarize(days, req),
        },
        "diagnostics": {
            "eligible_by_type": {t: len(v) for t, v in elig_by_type.items()},
            "pool_by_type": {t: len(v) for t, v in pools.items()},
            "max_repeats_used": chosen_caps, "filtered_out": dict(stats),
        },
    }
    return plan
