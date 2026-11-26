import pytest

from app.services.filters import filter_recipes
from app.services.matching import ingredient_matches, matching_ingredient_ids
from app.services.planner import PlanInputError, arrange, generate_plan
from tests.conftest import make_req


def all_meals(plan):
    return [m for d in plan["days"] for m in d["meals"]]


def test_matching_is_conservative_but_not_silly(store):
    ing = store.ingredients
    assert ingredient_matches("tomatoes", ing["tomato"])
    assert ingredient_matches("milk", ing["milk"]) and not ingredient_matches("milk", ing["coconut_milk"])
    assert ingredient_matches("nuts", ing["peanuts"]) and ingredient_matches("nuts", ing["almonds"])
    assert ingredient_matches("gluten", ing["pasta"]) and ingredient_matches("seafood", ing["shrimp"])


def test_plan_has_exact_days_and_meals(store):
    p = generate_plan(make_req(days=5, meals_per_day=4), store)
    assert len(p["days"]) == 5
    assert all([m["slot"] for m in d["meals"]] == ["breakfast", "lunch", "dinner", "snack"] for d in p["days"])


def test_variety_no_repeats_when_enough_dishes(store):
    p = generate_plan(make_req(days=5, meals_per_day=3, budget=200), store)
    for slot in ("breakfast",):
        names = [m["recipe_id"] for m in all_meals(p) if m["slot"] == slot]
        assert len(set(names)) == len(names)
    mains = [m["recipe_id"] for m in all_meals(p) if m["slot"] in ("lunch", "dinner")]
    assert len(set(mains)) == len(mains)


def test_repetition_is_explained_when_unavoidable(store):
    p = generate_plan(make_req(days=30, meals_per_day=4, budget=2000, people=1), store)
    counts = {}
    for m in all_meals(p):
        counts[m["recipe_id"]] = counts.get(m["recipe_id"], 0) + 1
    assert max(counts.values()) > 1
    assert any("appears" in n for n in p["notes"])


def test_no_adjacent_repeats():
    import random
    seq = arrange({"a": 3, "b": 3, "c": 2}, random.Random(0))
    assert all(x != y for x, y in zip(seq, seq[1:]))


@pytest.mark.parametrize("pref,banned_rank", [("vegan", 0), ("vegetarian", 1)])
def test_diet_preferences_are_enforced(store, pref, banned_rank):
    p = generate_plan(make_req(food_preference=pref, budget=120), store)
    assert all(store.recipe_by_id[m["recipe_id"]].diet_rank <= banned_rank for m in all_meals(p))


@pytest.mark.parametrize("allergy", ["peanuts", "dairy", "gluten", "egg", "shellfish", "soy", "sesame"])
def test_allergies_never_appear(store, allergy):
    p = generate_plan(make_req(allergies=[allergy], budget=150, seed=3), store)
    bad = matching_ingredient_ids([allergy], store)
    for m in all_meals(p):
        assert not (bad & store.recipe_by_id[m["recipe_id"]].ingredients.keys())
    shop_ids = {i["id"] for g in p["shopping_list"]["groups"] for i in g["items"]}
    assert not (bad & shop_ids)


def test_dislikes_and_equipment(store):
    p = generate_plan(make_req(dislikes=["chicken", "biryani"], budget=150), store)
    assert all("chicken" not in store.recipe_by_id[m["recipe_id"]].ingredients for m in all_meals(p))
    elig, stats = filter_recipes(store, make_req(equipment=["stovetop"]), apply_time=False)
    assert all("oven" not in r.equipment for r in elig) and stats["equipment"] > 0


def test_budget_is_respected_when_feasible(store):
    p = generate_plan(make_req(budget=45), store)
    assert p["status"] == "ok" and p["shopping_list"]["total_cost"] <= 45


def test_over_budget_is_explicit_never_silent(store):
    p = generate_plan(make_req(budget=3), store)
    assert p["status"] == "over_budget"
    assert p["shopping_list"]["total_cost"] > 3
    assert p["warnings"][0].startswith("Your budget") and p["suggestions"]


def test_cheaper_budget_gives_cheaper_plan(store):
    rich = generate_plan(make_req(budget=500), store)["shopping_list"]["total_cost"]
    tight = generate_plan(make_req(budget=45), store)["shopping_list"]["total_cost"]
    assert tight <= 45 and tight <= rich


def test_pantry_reduces_cost(store):
    base = generate_plan(make_req(budget=80, seed=5), store)["summary"]["grocery_total"]
    pantry = generate_plan(make_req(budget=80, seed=5, available_ingredients=[{"name": "rice"}, {"name": "oil"}, {"name": "onions"}]), store)
    assert pantry["summary"]["grocery_total"] <= base


def test_unrecognised_terms_produce_warnings(store):
    p = generate_plan(make_req(allergies=["kiwi"], available_ingredients=[{"name": "dragon scales"}], budget=100), store)
    assert any("kiwi" in w for w in p["warnings"]) and any("dragon" in w for w in p["warnings"])


def test_impossible_filters_raise_clear_error(store):
    with pytest.raises(PlanInputError):
        generate_plan(make_req(equipment=[], allergies=["chickpeas"], budget=100), store)  # only no-cook dish left is hummus plate


def test_nutrition_summary_present_and_cost_consistent(store):
    p = generate_plan(make_req(budget=100), store)
    n = p["summary"]["nutrition"]
    assert n["avg_per_person_day"]["kcal"] > 0 and n["reference_targets"]["kcal"] > 0
    assert p["summary"]["meals_cost"] == pytest.approx(sum(m["cost"] for m in all_meals(p)), abs=0.05)


def test_currency_scaling(store):
    usd = generate_plan(make_req(budget=60, currency="USD", seed=2), store)["summary"]["meals_cost"]
    inr = generate_plan(make_req(budget=60 * 83, currency="INR", seed=2), store)["summary"]["meals_cost"]
    assert inr == pytest.approx(usd * 83, rel=0.02)


def test_feedback_changes_ranking(store):
    base = generate_plan(make_req(budget=300, days=1, meals_per_day=2, seed=1), store)
    disliked = {base["days"][0]["meals"][0]["recipe_id"]: "dislike"}
    again = generate_plan(make_req(budget=300, days=1, meals_per_day=2, seed=1), store, feedback=disliked)
    assert next(iter(disliked)) not in [m["recipe_id"] for m in all_meals(again)]


def test_repeats_rotate_instead_of_repeating_each_day():
    import random
    seq = arrange({"a": 4, "b": 4, "c": 4}, random.Random(1))
    days = [tuple(seq[i:i + 2]) for i in range(0, 12, 2)]   # 2 main meals per day
    assert all(d1 != d2 for d1, d2 in zip(days, days[1:]))
    assert all(x != y for x, y in zip(seq, seq[1:]))
