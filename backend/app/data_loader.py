"""Loads the ingredient/recipe/currency datasets and derives nutrition, cost, diet and allergens."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import pandas as pd

from . import config

DIET_RANK = {"vegan": 0, "vegetarian": 1, "non_veg": 2}
NUTRIENTS = ("kcal", "protein", "carbs", "fat", "fiber")
VALID_MEALS = {"breakfast", "main", "snack"}
DEFAULT_SOURCE = ("Starter recipe written for this project. Quantities are approximate and have not been "
                  "verified against a published source.")
CUISINE_LABELS = {
    "kerala": "Kerala", "indian": "Indian", "mediterranean": "Mediterranean", "italian": "Italian",
    "mexican": "Mexican", "chinese": "Chinese", "japanese": "Japanese", "thai": "Thai",
    "middle_eastern": "Middle Eastern", "south_indian": "South Indian", "american": "American", "west_african": "West African",
    "korean": "Korean",
}


class DataError(ValueError):
    pass


@dataclass(frozen=True, eq=False)
class Ingredient:
    id: str
    name: str
    category: str
    per100: dict            # nutrient -> float | None (per 100 g)
    price_usd_kg: float | None
    diet: str
    allergens: frozenset
    piece_g: float | None
    pack_g: float


@dataclass(eq=False)
class Recipe:
    id: str
    name: str
    cuisine: str
    meals: list
    time_min: int
    equipment: list
    ingredients: dict       # ingredient id -> grams per serving
    steps: list
    source: str
    diet: str = "vegan"
    diet_rank: int = 0
    allergens: frozenset = frozenset()
    nutrition: dict | None = None      # per serving; None when any ingredient lacks data
    cost_usd: float | None = None      # per serving in USD with the dataset prices
    description: str = ""
    text: str = ""
    staple: str = "none"        # dominant grain/flour ingredient (recipe type)
    main_protein: str = "none"  # dominant protein/dairy/egg ingredient


def _num(v):
    return None if pd.isna(v) else float(v)


class DataStore:
    def __init__(self, data_dir: Path | str | None = None):
        d = Path(data_dir or config.DATA_DIR)
        self.ingredients = self._load_ingredients(d / "ingredients.csv")
        self.currencies = json.loads((d / "currencies.json").read_text(encoding="utf-8"))
        self.recipes = self._load_recipes(d / "recipes.json")
        self.recipe_by_id = {r.id: r for r in self.recipes}
        self.cuisines = sorted({r.cuisine for r in self.recipes})

    def _load_ingredients(self, path: Path) -> dict:
        df = pd.read_csv(path, dtype={"allergens": str})
        out = {}
        for row in df.to_dict("records"):
            iid = row["id"]
            if iid in out:
                raise DataError(f"Duplicate ingredient id: {iid}")
            if row["diet"] not in DIET_RANK:
                raise DataError(f"Ingredient {iid}: bad diet value {row['diet']!r}")
            pack = _num(row.get("pack_g"))
            if not pack or pack <= 0:
                raise DataError(f"Ingredient {iid}: pack_g must be positive")
            allergens = row.get("allergens")
            tags = frozenset(a.strip() for a in allergens.split(";") if a.strip()) if isinstance(allergens, str) else frozenset()
            out[iid] = Ingredient(
                id=iid, name=row["name"], category=row["category"],
                per100={n: _num(row.get(n)) for n in NUTRIENTS},
                price_usd_kg=_num(row.get("price_usd_kg")), diet=row["diet"], allergens=tags,
                piece_g=_num(row.get("piece_g")), pack_g=pack,
            )
        return out

    def _load_recipes(self, path: Path) -> list:
        raw = json.loads(path.read_text(encoding="utf-8"))
        recipes, seen = [], set()
        for rec in raw:
            rid = rec["id"]
            if rid in seen:
                raise DataError(f"Duplicate recipe id: {rid}")
            seen.add(rid)
            if not set(rec["meals"]) <= VALID_MEALS or not rec["meals"]:
                raise DataError(f"Recipe {rid}: invalid meals {rec['meals']}")
            for iid, g in rec["ingredients"].items():
                if iid not in self.ingredients:
                    raise DataError(f"Recipe {rid}: unknown ingredient {iid!r}")
                if g <= 0:
                    raise DataError(f"Recipe {rid}: quantity for {iid} must be positive")
            r = Recipe(id=rid, name=rec["name"], cuisine=rec["cuisine"], meals=list(rec["meals"]),
                       time_min=int(rec["time_min"]), equipment=list(rec.get("equipment", [])),
                       ingredients=dict(rec["ingredients"]), steps=list(rec["steps"]),
                       source=rec.get("source", DEFAULT_SOURCE))
            self._derive(r)
            recipes.append(r)
        return recipes

    def _derive(self, r: Recipe) -> None:
        ings = [self.ingredients[i] for i in r.ingredients]
        r.diet_rank = max(DIET_RANK[i.diet] for i in ings)
        r.diet = {v: k for k, v in DIET_RANK.items()}[r.diet_rank]
        r.allergens = frozenset().union(*(i.allergens for i in ings))
        totals, complete = dict.fromkeys(NUTRIENTS, 0.0), True
        for iid, g in r.ingredients.items():
            for n in NUTRIENTS:
                v = self.ingredients[iid].per100[n]
                if v is None:
                    complete = False
                else:
                    totals[n] += v * g / 100.0
        r.nutrition = {n: round(v, 1) for n, v in totals.items()} if complete else None
        prices = [(self.ingredients[i].price_usd_kg, g) for i, g in r.ingredients.items()]
        r.cost_usd = None if any(p is None for p, _ in prices) else sum(p * g / 1000.0 for p, g in prices)
        top = sorted(r.ingredients, key=r.ingredients.get, reverse=True)[:3]
        label = CUISINE_LABELS.get(r.cuisine, r.cuisine.replace("_", " ").title())
        r.description = (f"{label} dish with {', '.join(self.ingredients[i].name.lower() for i in top)}, "
                         f"ready in about {r.time_min} minutes.")
        def dominant(cats):
            c = [i for i in r.ingredients if self.ingredients[i].category in cats]
            return max(c, key=r.ingredients.get) if c else "none"
        r.staple = dominant({"Grains & cereals"})
        r.main_protein = dominant({"Protein", "Dairy & eggs"})
        r.text = (f"{r.cuisine} {r.cuisine} staple_{r.staple} staple_{r.staple} protein_{r.main_protein} "
                  f"protein_{r.main_protein} " + " ".join(r.ingredients))


@lru_cache(maxsize=1)
def get_store() -> DataStore:
    return DataStore()
