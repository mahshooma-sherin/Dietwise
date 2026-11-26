"""Matching free-text allergy/dislike/pantry terms to ingredients (conservative: prefers over-excluding)."""
from __future__ import annotations

import re

ALLERGEN_SYNONYMS = {
    "nut": {"tree_nut", "peanut"}, "tree_nut": {"tree_nut"}, "peanut": {"peanut"}, "groundnut": {"peanut"},
    "milk": {"dairy"}, "lactose": {"dairy"}, "dairy": {"dairy"}, "egg": {"egg"},
    "wheat": {"gluten"}, "gluten": {"gluten"}, "soy": {"soy"}, "soya": {"soy"}, "sesame": {"sesame"},
    "fish": {"fish"}, "shellfish": {"shellfish"}, "seafood": {"fish", "shellfish"}, "mustard": {"mustard"},
}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z ]", " ", text.lower()).strip()


def _singular(w: str) -> str:
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("oes"):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def term_tokens(term: str) -> list:
    return [_singular(w) for w in _norm(term).split()]


def ingredient_matches(term: str, ing) -> bool:
    """True if a user term (e.g. 'peanuts', 'dairy', 'tomatoes') refers to this ingredient."""
    toks = term_tokens(term)
    if not toks:
        return False
    joined = "_".join(toks)
    allergens = ALLERGEN_SYNONYMS.get(joined)
    if allergens:
        return bool(ing.allergens & allergens) or joined == ing.id
    if joined == ing.id:
        return True
    name_toks = {_singular(w) for w in _norm(ing.name).split()} | set(ing.id.split("_"))
    return all(t in name_toks for t in toks)


def matching_ingredient_ids(terms, store) -> set:
    return {i.id for i in store.ingredients.values() if any(ingredient_matches(t, i) for t in terms)}


def recipe_name_matches(term: str, recipe) -> bool:
    toks = term_tokens(term)
    name_toks = {_singular(w) for w in _norm(recipe.name).split()}
    return bool(toks) and all(t in name_toks for t in toks)


def resolve_ingredient(term: str, store) -> str | None:
    """Resolve a pantry term to exactly one ingredient id, or None if unknown/ambiguous."""
    toks = term_tokens(term)
    if not toks:
        return None
    joined = "_".join(toks)
    if joined in store.ingredients:
        return joined
    for ing in store.ingredients.values():
        if [_singular(w) for w in _norm(ing.name).split()] == toks:
            return ing.id
    cands = [i.id for i in store.ingredients.values()
             if all(t in ({_singular(w) for w in _norm(i.name).split()} | set(i.id.split("_"))) for t in toks)]
    return cands[0] if len(cands) == 1 else None
