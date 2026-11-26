"""Hard safety filters. These run BEFORE ranking; similarity scores can never override them."""
from __future__ import annotations

from collections import Counter

from .. import config
from .matching import matching_ingredient_ids, recipe_name_matches

ALLOWED_DIET_RANK = {"vegan": 0, "vegetarian": 1, "non_vegetarian": 2}


def filter_recipes(store, req, excluded_ids=frozenset(), apply_time=True):
    stats, out = Counter(), []
    cap = config.TIME_CAPS[req.max_cook_time] if apply_time else None
    equip = set(req.equipment)
    allergy_ids = matching_ingredient_ids(req.allergies, store)
    dislike_ids = matching_ingredient_ids(req.dislikes, store)
    for r in store.recipes:
        if r.diet_rank > ALLOWED_DIET_RANK[req.food_preference]:
            stats["diet"] += 1
        elif allergy_ids & r.ingredients.keys():
            stats["allergy"] += 1
        elif dislike_ids & r.ingredients.keys() or any(recipe_name_matches(t, r) for t in req.dislikes):
            stats["dislike"] += 1
        elif r.id in excluded_ids:
            stats["disliked_before"] += 1
        elif not set(r.equipment) <= equip:
            stats["equipment"] += 1
        elif cap is not None and r.time_min > cap:
            stats["time"] += 1
        else:
            out.append(r)
    return out, stats


def assert_plan_safe(recipes, req, store):
    """Defence in depth: re-check the final plan against allergies and diet."""
    bad = matching_ingredient_ids(req.allergies, store)
    for r in recipes:
        if bad & r.ingredients.keys():
            raise AssertionError(f"Safety check failed: {r.id} contains an excluded ingredient")
        if r.diet_rank > ALLOWED_DIET_RANK[req.food_preference]:
            raise AssertionError(f"Safety check failed: {r.id} violates the diet preference")
