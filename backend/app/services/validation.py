"""Input validation beyond what pydantic can check (needs the datasets)."""
from __future__ import annotations

import math

from .. import config
from .matching import ingredient_matches, matching_ingredient_ids, resolve_ingredient


def validate_request(req, store):
    """Returns (errors, warnings, pantry) where pantry maps ingredient id -> grams (math.inf = plenty)."""
    errors, warnings, pantry = [], [], {}
    if req.currency not in store.currencies:
        errors.append(f"Unsupported currency '{req.currency}'. Choose one of: {', '.join(sorted(store.currencies))}.")
    if req.cuisine != "any" and req.cuisine not in store.cuisines:
        errors.append(f"Unknown cuisine '{req.cuisine}'.")
    bad_eq = [e for e in req.equipment if e not in config.EQUIPMENT]
    if bad_eq:
        errors.append(f"Unknown equipment: {', '.join(bad_eq)}.")
    for iid, price in req.price_overrides.items():
        if iid not in store.ingredients:
            errors.append(f"price_overrides: unknown ingredient id '{iid}'.")
        elif price < 0:
            errors.append(f"price_overrides: price for '{iid}' cannot be negative.")
    if errors:
        return errors, warnings, pantry

    for label, terms in (("Allergy/restriction", req.allergies), ("Disliked food", req.dislikes)):
        for t in terms:
            matched_ing = any(ingredient_matches(t, i) for i in store.ingredients.values())
            matched_name = label == "Disliked food" and any(
                t.lower() in r.name.lower() for r in store.recipes)
            if not matched_ing and not matched_name:
                warnings.append(f"'{t}' did not match any ingredient in the dataset, so it excludes nothing. "
                                f"Check the spelling if this is a real allergy.")

    unsafe = matching_ingredient_ids(req.allergies, store)
    for item in req.available_ingredients:
        iid = resolve_ingredient(item.name, store)
        if iid is None:
            warnings.append(f"Pantry item '{item.name}' was not recognised (or is ambiguous) and was ignored.")
        elif iid in unsafe:
            warnings.append(f"Pantry item '{item.name}' conflicts with your allergies and will not be used.")
        else:
            pantry[iid] = pantry.get(iid, 0.0) + item.grams if item.grams else math.inf
    return errors, warnings, pantry
