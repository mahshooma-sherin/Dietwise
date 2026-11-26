"""Consolidated shopping list: scale -> sum -> subtract pantry -> round to packs -> price -> group."""
from __future__ import annotations

import math
from collections import defaultdict

from ..units import format_qty, round_up_to_pack

CATEGORY_ORDER = ["Grains & cereals", "Protein", "Dairy & eggs", "Nuts & seeds", "Vegetables", "Fruits",
                  "Pantry & oils", "Spices & herbs"]


def aggregate(meals) -> dict:
    """meals: iterable of (recipe, servings). Returns ingredient id -> total grams."""
    totals = defaultdict(float)
    for recipe, servings in meals:
        for iid, g in recipe.ingredients.items():
            totals[iid] += g * servings
    return dict(totals)


def build_shopping_list(store, meals, pantry, prices, round_to_packs=True) -> dict:
    need = aggregate(meals)
    by_cat, total = defaultdict(list), 0.0
    for iid, needed in need.items():
        ing = store.ingredients[iid]
        have = pantry.get(iid, 0.0)
        to_buy = max(0.0, needed - have)
        if to_buy <= 1e-9:
            purchase = 0.0
        elif round_to_packs:
            purchase = round_up_to_pack(to_buy, ing.pack_g)
        else:
            purchase = float(math.ceil(to_buy - 1e-9))
        cost = purchase / 1000.0 * prices.get(iid, 0.0)
        total += cost
        unlimited = math.isinf(have)
        by_cat[ing.category].append({
            "id": iid, "name": ing.name, "category": ing.category,
            "needed_g": round(needed, 1), "needed_display": format_qty(needed, ing.piece_g),
            "available_g": None if unlimited else round(have, 1), "available_unlimited": unlimited,
            "to_buy_g": round(to_buy, 1), "purchase_g": round(purchase, 1),
            "purchase_display": format_qty(purchase, ing.piece_g) if purchase else "Already have enough",
            "estimated_cost": round(cost, 2), "unit": "g",
        })
    groups = []
    for cat in sorted(by_cat, key=lambda c: CATEGORY_ORDER.index(c) if c in CATEGORY_ORDER else 99):
        groups.append({"category": cat, "items": sorted(by_cat[cat], key=lambda x: x["name"])})
    return {"groups": groups, "total_cost": round(total, 2), "item_count": len(need)}


def shopping_list_csv(shopping: dict, currency: str) -> str:
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["category", "ingredient", "total_needed_g", "already_have_g", "to_buy_g", "purchase_g",
                f"estimated_cost_{currency}"])
    for g in shopping["groups"]:
        for i in g["items"]:
            have = "plenty" if i["available_unlimited"] else (i["available_g"] or 0)
            w.writerow([g["category"], i["name"], i["needed_g"], have, i["to_buy_g"], i["purchase_g"],
                        i["estimated_cost"]])
    w.writerow([])
    w.writerow(["TOTAL", "", "", "", "", "", shopping["total_cost"]])
    return buf.getvalue()
