import math

import pytest

from app.services.cost import build_price_table
from app.services.grocery import aggregate, build_shopping_list


def prices(store, **kw):
    p, _ = build_price_table(store, "USD", 1.0, {}, kw.get("free", set()))
    return p


def item(shop, iid):
    return next(i for g in shop["groups"] for i in g["items"] if i["id"] == iid)


def test_aggregation_sums_across_recipes_and_scales_servings(store):
    a, b = store.recipe_by_id["dal_tadka_rice"], store.recipe_by_id["rajma_chawal"]
    totals = aggregate([(a, 2), (b, 3)])
    assert totals["rice"] == pytest.approx(70 * 2 + 70 * 3)
    assert totals["onion"] == pytest.approx(30 * 2 + 50 * 3)
    assert totals["kidney_beans"] == pytest.approx(70 * 3)


def test_pantry_subtraction_and_pack_rounding(store):
    a = store.recipe_by_id["dal_tadka_rice"]
    shop = build_shopping_list(store, [(a, 10)], {"rice": 300.0}, prices(store), True)
    rice = item(shop, "rice")
    assert rice["needed_g"] == 700 and rice["to_buy_g"] == 400 and rice["purchase_g"] == 500
    assert rice["estimated_cost"] == pytest.approx(0.5 * 1.6, abs=0.01)


def test_unlimited_pantry_costs_nothing(store):
    a = store.recipe_by_id["dal_tadka_rice"]
    shop = build_shopping_list(store, [(a, 4)], {"rice": math.inf}, prices(store, free={"rice"}), True)
    rice = item(shop, "rice")
    assert rice["to_buy_g"] == 0 and rice["estimated_cost"] == 0 and rice["available_unlimited"]


def test_exact_mode_buys_only_what_is_needed(store):
    a = store.recipe_by_id["dal_tadka_rice"]
    shop = build_shopping_list(store, [(a, 3)], {}, prices(store), False)
    assert item(shop, "rice")["purchase_g"] == 210


def test_total_is_sum_of_items(store):
    a = store.recipe_by_id["chicken_curry_rice"]
    shop = build_shopping_list(store, [(a, 5)], {}, prices(store), True)
    assert shop["total_cost"] == pytest.approx(sum(i["estimated_cost"] for g in shop["groups"] for i in g["items"]), abs=0.05)
