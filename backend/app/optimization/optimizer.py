"""Integer program (HiGHS via scipy.optimize.milp) that decides HOW MANY TIMES each dish is cooked.

It models the real shopping bill, so ingredient reuse and pack sizes are optimised, not guessed:

Variables
  u[r,k] in {0,1}   dish r is cooked at least k times (k = 1..cap). The k-th copy earns
                    score - REPEAT_PENALTY*(k-1), so a repeat is always worth less than a fresh dish.
  p[i]   integer>=0 packs of ingredient i to buy (or grams, when round_to_packs is off).
Constraints
  per meal type:  sum of u = number of slots;   u[r,k] <= u[r,k-1]
  per ingredient: sum(grams_per_serving * people * u) - pack_size * p[i] <= grams already at home
  shopping bill:  sum(price_per_pack * p[i]) <= budget          (exactly what the grocery list will charge)
Objective (minimise)
  -sum(score*u) + COST_WEIGHT * bill / ref            ('balanced': quality first, cost as a tie-breaker)
  bill                                                ('min_cost': cheapest feasible plan, used for feasibility)
Ingredients the user has "plenty" of cost nothing and get no variable.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

from .. import config


def solve_counts(spec: dict, budget: float | None, mode: str = "balanced"):
    """spec: {types:{t:{slots,pool,cap}}, score, ingredients:{rid:{iid:grams/serving}}, people, pack, price,
    have, free, round, ref}.  Returns {t: {recipe_id: count}} or None if infeasible."""
    P = spec["people"]
    var_u, n = {}, 0
    for t, ts in spec["types"].items():
        for rid in ts["pool"]:
            for k in range(1, ts["cap"] + 1):
                var_u[(t, rid, k)] = n
                n += 1

    ing_ids = sorted({i for ts in spec["types"].values() for rid in ts["pool"] for i in spec["ingredients"][rid]
                      if i not in spec["free"]})
    var_p, ub_p = {}, {}
    for i in ing_ids:
        var_p[i] = n
        n += 1
        pack = spec["pack"][i]
        worst = sum(ts["slots"] * max((spec["ingredients"][rid].get(i, 0.0) for rid in ts["pool"]), default=0.0) * P
                    for ts in spec["types"].values())
        ub_p[i] = max(0.0, math.ceil(max(0.0, worst - spec["have"].get(i, 0.0)) / pack) + 1)

    ref = max(spec["ref"], 1e-9)
    c = np.zeros(n)
    for (t, rid, k), col in var_u.items():
        if mode != "min_cost":
            c[col] = -(spec["score"][rid] - config.REPEAT_PENALTY * (k - 1))
    pack_cost = {i: spec["price"][i] / 1000.0 * spec["pack"][i] for i in ing_ids}
    for i, col in var_p.items():
        c[col] = pack_cost[i] if mode == "min_cost" else config.COST_WEIGHT * pack_cost[i] / ref

    rows, cols, vals, lb, ub = [], [], [], [], []

    def add(entries, lo, hi):
        r = len(lb)
        for col, v in entries:
            rows.append(r)
            cols.append(col)
            vals.append(v)
        lb.append(lo)
        ub.append(hi)

    for t, ts in spec["types"].items():
        add([(var_u[(t, rid, k)], 1.0) for rid in ts["pool"] for k in range(1, ts["cap"] + 1)], ts["slots"], ts["slots"])
        for rid in ts["pool"]:
            for k in range(2, ts["cap"] + 1):
                add([(var_u[(t, rid, k)], 1.0), (var_u[(t, rid, k - 1)], -1.0)], -np.inf, 0.0)
    usage = {i: [] for i in ing_ids}
    for (t, rid, k), col in var_u.items():
        for i, g in spec["ingredients"][rid].items():
            if i in usage:
                usage[i].append((col, g * P))
    for i in ing_ids:
        add(usage[i] + [(var_p[i], -spec["pack"][i])], -np.inf, spec["have"].get(i, 0.0))
    if budget is not None:
        add([(col, pack_cost[i]) for i, col in var_p.items()], -np.inf, budget)

    integrality = np.ones(n)
    lower, upper = np.zeros(n), np.ones(n)
    for i, col in var_p.items():
        upper[col] = ub_p[i]
        integrality[col] = 1 if spec["round"] else 0
    A = coo_matrix((vals, (rows, cols)), shape=(len(lb), n)).tocsr()
    res = milp(c, constraints=LinearConstraint(A, lb, ub), integrality=integrality,
               bounds=Bounds(lower, upper), options={"time_limit": config.SOLVER_TIME_LIMIT, "mip_rel_gap": 1e-2})
    if res.x is None:
        return None
    x = np.round(res.x[:len(var_u)])
    counts = {t: {} for t in spec["types"]}
    for (t, rid, k), col in var_u.items():
        if x[col] > 0.5:
            counts[t][rid] = counts[t].get(rid, 0) + 1
    return counts
