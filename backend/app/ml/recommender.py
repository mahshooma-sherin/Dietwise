"""Content-based recipe recommender.

ML part: TF-IDF vectors over each recipe's cuisine + ingredient tokens, and cosine similarity between a
recipe and a *user profile vector*. The profile is built from the chosen cuisine, pantry ingredients and the
user's stored feedback (liked / cook-again recipes pull the profile towards them; disliked ones push away).
Rule part: goal fit, time fit, cost fit and pantry overlap are transparent formulas, blended with fixed
weights from config.WEIGHTS. Hard restrictions are NOT handled here (see services/filters.py).
"""
from __future__ import annotations

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .. import config
from ..data_loader import CUISINE_LABELS

TYPICAL_KCAL = {"breakfast": 350.0, "main": 600.0, "snack": 180.0}
GOAL_LABELS = {"balanced": "Balanced macros", "high_protein": "High protein per calorie",
               "high_fiber": "High fiber per calorie", "weight_management": "Filling for its calories"}


def slot_type(recipe) -> str:
    return recipe.meals[0]


def goal_fit(recipe, goal: str) -> float:
    """0..1 score of how well a recipe's nutrition matches the goal (0.5 when data is missing)."""
    n = recipe.nutrition
    if not n or n["kcal"] <= 0:
        return 0.5
    kcal = n["kcal"]
    p_share, c_share, f_share = 4 * n["protein"] / kcal, 4 * n["carbs"] / kcal, 9 * n["fat"] / kcal
    fiber_per100 = n["fiber"] / kcal * 100
    if goal == "high_protein":
        return float(min(1.0, p_share / 0.30))
    if goal == "high_fiber":
        return float(min(1.0, fiber_per100 / 3.0))
    if goal == "weight_management":
        typical = TYPICAL_KCAL[slot_type(recipe)]
        cal_fit = 1.0 - min(1.0, max(0.0, kcal - typical) / typical)
        return float(0.4 * cal_fit + 0.3 * min(1.0, p_share / 0.25) + 0.3 * min(1.0, fiber_per100 / 2.5))
    l1 = abs(p_share - 0.18) + abs(c_share - 0.52) + abs(f_share - 0.30)
    return float(0.8 * (1.0 - min(1.0, l1 / 0.8)) + 0.2 * min(1.0, fiber_per100 / 2.5))


class Recommender:
    def __init__(self, recipes):
        self.recipes = recipes
        self.idx = {r.id: i for i, r in enumerate(recipes)}
        self.vec = TfidfVectorizer(token_pattern=r"[a-z_]+", sublinear_tf=True)
        self.X = self.vec.fit_transform([r.text for r in recipes])
        # Diversity score = 1 - similarity. Similarity blends ingredient TF-IDF cosine with whether two recipes
        # share cuisine, staple (rice/chapati/...) and main protein, so "rice + dal" twice reads as similar.
        def same(vals):
            a = np.array(vals)
            return (a[:, None] == a[None, :]).astype(float)
        m = config.SIMILARITY_MIX
        self.sim = (m["tfidf"] * cosine_similarity(self.X) + m["cuisine"] * same([r.cuisine for r in recipes])
                    + m["staple"] * same([r.staple for r in recipes]) + m["protein"] * same([r.main_protein for r in recipes]))

    def similarity(self, recipes) -> np.ndarray:
        ix = [self.idx[r.id] for r in recipes]
        return self.sim[np.ix_(ix, ix)]

    def _centroid(self, items):
        """items: list of (recipe_id, weight) -> weighted mean TF-IDF row (sparse)."""
        if not items:
            return None
        total = sum(w for _, w in items)
        acc = csr_matrix((1, self.X.shape[1]))
        for rid, w in items:
            acc = acc + self.X[self.idx[rid]] * (w / total)
        return acc

    def score(self, candidates, req, feedback, cost_per_serving, pantry_ids) -> dict:
        feedback = feedback or {}
        n = len(candidates)
        Xc = self.X[[self.idx[r.id] for r in candidates]]

        parts = []
        if req.cuisine != "any":
            parts.append(self.vec.transform([req.cuisine]))
        if pantry_ids:
            parts.append(0.5 * self.vec.transform([" ".join(sorted(pantry_ids))]))
        liked = self._centroid([(rid, 1.5 if rt == "cook_again" else 1.0)
                                for rid, rt in feedback.items() if rt in ("like", "cook_again") and rid in self.idx])
        if liked is not None:
            parts.append(liked)
        sim = np.zeros(n)
        if parts:
            profile = parts[0]
            for p in parts[1:]:
                profile = profile + p
            if profile.nnz:
                sim = cosine_similarity(Xc, profile).ravel()
        if sim.max() > 0:
            sim = sim / sim.max()
        disliked = self._centroid([(rid, 1.0) for rid, rt in feedback.items() if rt == "dislike" and rid in self.idx])
        if disliked is not None:
            sim = sim - config.DISLIKE_SIMILARITY_PENALTY * cosine_similarity(Xc, disliked).ravel()

        costs = np.array([cost_per_serving[r.id] for r in candidates])
        span = costs.max() - costs.min()
        cost_fit = 1.0 - (costs - costs.min()) / span if span > 1e-12 else np.ones(n)
        pantry_set = set(pantry_ids or [])

        w, out = config.WEIGHTS, {}
        for i, r in enumerate(candidates):
            comps = {
                "similarity": float(sim[i]),
                "goal": goal_fit(r, req.nutrition_goal),
                "time": 1.0 - min(r.time_min, 90) / 90.0,
                "cost": float(cost_fit[i]),
                "pantry": sum(1 for x in r.ingredients if x in pantry_set) / len(r.ingredients),
                "cuisine": 1.0 if req.cuisine != "any" and r.cuisine == req.cuisine else 0.0,
            }
            boost = config.FEEDBACK_BOOST.get(feedback.get(r.id, ""), 0.0)
            score = sum(w[k] * comps[k] for k in w) + boost
            reasons = []
            if comps["cuisine"]:
                reasons.append(f"{CUISINE_LABELS.get(r.cuisine, r.cuisine)} cuisine")
            if comps["goal"] >= 0.7:
                reasons.append(GOAL_LABELS[req.nutrition_goal])
            if boost:
                reasons.append("You rated this highly")
            if comps["pantry"] >= 0.3:
                reasons.append("Uses ingredients you have")
            if comps["cost"] >= 0.75:
                reasons.append("Budget-friendly")
            out[r.id] = {"score": float(score), "components": comps, "reasons": reasons}
        return out


_CACHE: dict = {}


def get_recommender(store) -> Recommender:
    key = id(store)
    if key not in _CACHE:
        _CACHE.clear()
        _CACHE[key] = Recommender(store.recipes)
    return _CACHE[key]
