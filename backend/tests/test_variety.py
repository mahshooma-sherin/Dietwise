"""The 7-day, 3-meals-per-day scenario: 21 different meals, correct categories, preferences, grocery accuracy."""
import pytest

from app.services.grocery import aggregate
from app.services.planner import generate_plan
from tests.conftest import make_req

KW = dict(budget=300, currency="USD", food_preference="vegetarian", nutrition_goal="balanced", days=7, people=2,
          meals_per_day=3, cuisine="kerala")


def meals(plan):
    return [m for d in plan["days"] for m in d["meals"]]


def test_seven_days_21_unique_meals_in_right_categories(store):
    p = generate_plan(make_req(**KW, seed=11), store)
    ms = meals(p)
    assert len(p["days"]) == 7 and len(ms) == 21
    ids = [m["recipe_id"] for m in ms]
    assert len(set(ids)) == 21, "a recipe repeated although enough recipes exist"
    for m in ms:
        recipe = store.recipe_by_id[m["recipe_id"]]
        assert ("breakfast" if m["slot"] == "breakfast" else "main") in recipe.meals
    assert all(store.recipe_by_id[i].diet_rank <= 1 for i in ids)       # vegetarian respected
    assert not p["warnings"] or all("repeat" not in w for w in p["warnings"])


def test_no_day_matches_another_day(store):
    p = generate_plan(make_req(**KW, seed=3), store)
    days = [tuple(m["recipe_id"] for m in d["meals"]) for d in p["days"]]
    assert len(set(days)) == 7
    for a, b in zip(days, days[1:]):
        assert not set(a) & set(b)


def test_grocery_list_matches_final_plan_exactly(store):
    p = generate_plan(make_req(**KW, seed=5), store)
    need = aggregate([(store.recipe_by_id[m["recipe_id"]], m["servings"]) for m in meals(p)])
    listed = {i["id"]: i["needed_g"] for g in p["shopping_list"]["groups"] for i in g["items"]}
    assert set(listed) == set(need), "list contains ingredients from meals that are not in the plan (or misses some)"
    for iid, g in need.items():
        assert listed[iid] == pytest.approx(g, abs=0.1)
    assert p["shopping_list"]["total_cost"] == pytest.approx(
        sum(i["estimated_cost"] for g in p["shopping_list"]["groups"] for i in g["items"]), abs=0.05)


def test_seed_is_reproducible_and_new_seed_changes_plan(store):
    a = generate_plan(make_req(**KW, seed=1), store)
    b = generate_plan(make_req(**KW, seed=1), store)
    c = generate_plan(make_req(**KW, seed=2), store)
    ids = lambda p: [m["recipe_id"] for m in meals(p)]
    assert ids(a) == ids(b)
    assert ids(a) != ids(c)


def test_non_veg_plan_is_varied_and_allergy_safe(store):
    p = generate_plan(make_req(**{**KW, "food_preference": "non_vegetarian", "cuisine": "any", "budget": 400,
                                  "allergies": ["peanuts"]}, seed=4), store)
    ids = [m["recipe_id"] for m in meals(p)]
    assert len(set(ids)) == 21
    assert all("peanuts" not in store.recipe_by_id[i].ingredients for i in ids)


def test_tight_budget_keeps_variety_and_warns_instead_of_repeating(store):
    p = generate_plan(make_req(**{**KW, "budget": 20}, seed=2), store)
    assert p["status"] == "over_budget" and p["warnings"][0].startswith("Your budget")
    assert len({m["recipe_id"] for m in meals(p)}) == 21
    assert any("Allow repeated dishes" in s for s in p["suggestions"])


def test_repeats_only_when_user_allows_them_for_budget(store):
    p = generate_plan(make_req(**{**KW, "budget": 20, "allow_repeats_for_budget": True}, seed=2), store)
    assert len({m["recipe_id"] for m in meals(p)}) < 21


def test_not_enough_unique_dishes_is_explained(store):
    p = generate_plan(make_req(**{**KW, "food_preference": "vegan", "cuisine": "any", "days": 14, "budget": 900,
                                  "meals_per_day": 4, "allergies": ["peanuts", "soy", "gluten"]}, seed=1), store)
    assert any("repeat" in w and "Only" in w for w in p["warnings"])
