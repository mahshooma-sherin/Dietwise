"""Offline evaluation. Run:  python -m app.ml.evaluate

There are NO labelled user ratings in this project, so Precision@K cannot be computed honestly and is not
reported. Instead we measure what can be measured without labels, on a grid of scenarios:
  * constraint satisfaction (diet/allergy violations, budget compliance, exact day count)
  * variety (distinct-dish ratio, mean pairwise dissimilarity of the dishes used)
  * goal fit (mean goal_fit of the chosen dishes)
against a baseline that picks random eligible dishes (same hard filters, no ranking/optimizer/budget).
It also ablates MMR: mean pairwise dissimilarity of the candidate pool with vs without MMR.
"""
from __future__ import annotations

import itertools
import math
import random
import statistics as st

import numpy as np

from ..data_loader import get_store
from ..schemas import PlanRequest
from ..services.cost import build_price_table
from ..services.filters import filter_recipes
from ..services.grocery import build_shopping_list
from ..services.planner import _slots, generate_plan
from .diversity import mean_pairwise_distance, mmr
from .recommender import get_recommender, goal_fit


def scenarios():
    for pref, goal, days, people, budget in itertools.product(
            ["vegetarian", "non_vegetarian", "vegan"], ["balanced", "high_protein", "high_fiber", "weight_management"],
            [3, 7], [1, 4], [0.6, 1.5]):
        # budget expressed as USD per person per day so scenarios scale
        yield PlanRequest(budget=round(budget * 3 * days * people * 1.0, 2), food_preference=pref, nutrition_goal=goal,
                          days=days, people=people, seed=7, allergies=["peanuts"] if people == 4 else [])


def baseline(req, store, rec):
    rng = random.Random(req.seed)
    elig, _ = filter_recipes(store, req)
    used = []
    for t, sl in _slots(req).items():
        pool = [r for r in elig if t in r.meals]
        used += [rng.choice(pool) for _ in sl]
    prices, _ = build_price_table(store, req.currency, req.price_level, {}, set())
    shop = build_shopping_list(store, [(r, req.people) for r in used], {}, prices, True)
    return used, shop["total_cost"]


def max_possible_distinct(req, store):
    elig, _ = filter_recipes(store, req)
    return sum(min(len(sl), len([r for r in elig if t in r.meals])) for t, sl in _slots(req).items())


def metrics(used, req, rec, possible):
    ids = list({r.id: r for r in used}.values())
    return {
        "distinct_ratio": len(ids) / possible,
        "dissimilarity": mean_pairwise_distance(rec.similarity(ids)),
        "goal_fit": st.mean(goal_fit(r, req.nutrition_goal) for r in used),
    }


def main():
    store = get_store()
    rec = get_recommender(store)
    results = {}  # (system, budget level) -> list of metric dicts (+ budget flag)
    n = 0
    for req in scenarios():
        n += 1
        level = round(req.budget / (req.days * req.people), 1)  # USD per person per day
        possible = max_possible_distinct(req, store)
        plan = generate_plan(req, store, rec)
        used = [store.recipe_by_id[m["recipe_id"]] for d in plan["days"] for m in d["meals"]]
        assert len(plan["days"]) == req.days
        m = metrics(used, req, rec, possible)
        m["budget_met"] = plan["shopping_list"]["total_cost"] <= req.budget + 1e-9
        results.setdefault(("ours", level), []).append(m)
        b_used, b_cost = baseline(req, store, rec)
        m = metrics(b_used, req, rec, possible)
        m["budget_met"] = b_cost <= req.budget + 1e-9
        results.setdefault(("baseline", level), []).append(m)
    print(f"Scenarios: {n} (budget level = USD per person per day; distinct = distinct dishes / maximum possible given the filters)")
    print(f"{'system':10}{'$/person/day':>13}{'budget met':>12}{'distinct/possible':>17}{'dissimilarity':>15}{'goal fit':>10}")
    for (system, level), ms in sorted(results.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        print(f"{system:10}{level:13.1f}{100*st.mean(x['budget_met'] for x in ms):11.0f}%"
              f"{st.mean(x['distinct_ratio'] for x in ms):18.2f}"
              f"{st.mean(x['dissimilarity'] for x in ms):15.3f}"
              f"{st.mean(x['goal_fit'] for x in ms):10.3f}")

    # MMR ablation: pool of 6 mains chosen by relevance alone vs by MMR
    base_d, mmr_d = [], []
    for req in itertools.islice(scenarios(), 0, None, 5):
        elig, _ = filter_recipes(store, req)
        e = [r for r in elig if "main" in r.meals]
        if len(e) < 8:
            continue
        prices, _ = build_price_table(store, "USD", 1.0, {}, set())
        sc = rec.score(e, req, {}, {r.id: 1.0 for r in e}, set())
        rel = np.array([sc[r.id]["score"] for r in e])
        sim = rec.similarity(e)
        top = list(np.argsort(-rel)[:6])
        base_d.append(mean_pairwise_distance(sim[np.ix_(top, top)]))
        sel = mmr(rel, sim, 6, 0.7)
        mmr_d.append(mean_pairwise_distance(sim[np.ix_(sel, sel)]))
    print(f"\nMMR ablation over {len(base_d)} scenarios (pool of 6 mains, higher = more varied):")
    print(f"  top-6 by relevance only: {st.mean(base_d):.3f}")
    print(f"  MMR (lambda=0.7):        {st.mean(mmr_d):.3f}")
    print("\nNot measured: Precision@K / user-satisfaction (no labelled feedback exists yet).")


if __name__ == "__main__":
    main()
