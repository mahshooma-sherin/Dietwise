# DietWise - budget-first meal planning, worldwide

Enter a budget (in your currency), food preference, nutrition goal, days and people. DietWise returns a
**different meal for every slot**, the **ingredients and method for each dish**, a nutrition and cost summary, and
**one consolidated shopping list** whose total stays inside your budget. If the budget is too low it says so,
shows the cheapest plan it could build, and suggests what to change. It never silently overspends.

* Frontend: React 18 + TypeScript + Vite (plain CSS, no UI framework)
* Backend: Python, FastAPI, Pydantic, pandas, scikit-learn, SciPy (HiGHS MILP), SQLite
* Data: 71 ingredients, 63 recipes in 12 cuisines, 13 currencies (all in `backend/data/`, easy to extend)

## Run it

### Option 1: One-command Unified Server (Frontend + Backend on http://localhost:8000)
Runs the entire application from a single process — no separate frontend server needed:

```bash
python run.py
```
*(Automatically builds the React app into `frontend/dist` if not already built and launches `http://localhost:8000`)*

---

### Option 2: Development Mode (Hot Reloading)

```bash
# Backend (http://localhost:8000, API docs at /docs)
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend (http://localhost:5173, proxies /api to the backend)
cd frontend
npm install
npm run dev
```

Tests: `cd backend && pytest -q`.  Evaluation: `cd backend && python -m app.ml.evaluate` (takes a few minutes).

## Architecture

```
User inputs
  -> validation (pydantic + services/validation.py)
  -> HARD FILTERS: diet, allergies, dislikes, equipment, cooking time, dishes you disliked before   (services/filters.py)
  -> ML RANKING: TF-IDF + cosine similarity to a profile, blended with goal/time/cost/pantry scores  (ml/recommender.py)
  -> VARIETY: Maximal Marginal Relevance picks a relevant-but-diverse candidate pool                 (ml/diversity.py)
  -> OPTIMIZATION: integer program chooses dishes under the budget using the real shopping bill      (optimization/optimizer.py)
  -> arrange dishes across days (no neighbouring repeats) -> daily plan
  -> grocery aggregation: scale, sum, subtract pantry, round to packs, price, group                  (services/grocery.py)
  -> nutrition + cost summary -> saved in SQLite -> JSON to the React app
```

Backend layout: `app/api` routes, `app/services` planning/grocery/cost/nutrition, `app/ml` recommender + diversity +
evaluation, `app/optimization` the MILP, `app/db.py` SQLite, `data/` datasets, `tests/`.

## Data schema

`ingredients.csv` (one row per ingredient): `id, name, category, kcal, protein, carbs, fat, fiber` (per 100 g, raw/dry),
`price_usd_kg`, `diet` (vegan | vegetarian | non_veg), `allergens` (`;`-separated tags), `piece_g` (weight of one piece,
optional), `pack_g` (smallest practical pack).

`recipes.json`: `id, name, cuisine, meals` (breakfast | main | snack), `time_min`, `equipment`, `ingredients`
(ingredient id -> grams **per serving**), `steps`, optional `source`.

Everything else is **derived at load time**, never hand-typed: a recipe's diet (the strictest ingredient), allergens
(union of ingredient tags), nutrition and cost (sum over ingredients). The loader rejects unknown ingredient ids,
duplicate ids and non-positive quantities. Missing nutrition or price values are flagged, not guessed.

`currencies.json`: static, indicative USD exchange rates. Edit as needed.

## What is actually machine learning (and what is not)

| Step | Method | ML? |
|---|---|---|
| Allergy / diet / dislike / equipment filters | Exact rules. Similarity can never override them, and the final plan is re-checked | No (by design, for safety) |
| Relevance | TF-IDF over cuisine + ingredient tokens; cosine similarity to a user profile built from chosen cuisine, pantry and stored feedback (liked / cook-again recipes pull towards, disliked push away) | Yes |
| Goal, time, cost, pantry scores | Transparent formulas, blended with the weights in `config.WEIGHTS` | No |
| Variety | MMR over recipe-to-recipe cosine similarity | Yes (similarity-based diversification) |
| Budget and quantities | Mixed-integer linear program (HiGHS): integer pack counts per ingredient, dish repeat penalties, exact shopping bill <= budget | Optimization, not ML |
| Personalisation | Ratings are stored (SQLite) and used: dislikes remove a dish, likes/cook-again boost it and shift the profile vector. There is no trained preference model: that needs far more feedback than a prototype has | Content-based only |

## The optimizer

Dishes are chosen by count, not slot by slot (no symmetric slots, so it stays fast): `u[r,k]` = "dish r is cooked at
least k times", the k-th copy earns `score - 0.6*(k-1)`. Integer `p[i]` = packs of ingredient i, constrained so
packs cover total need minus pantry. The budget constraint is the exact bill the grocery list will print, so reusing
rice or onions across dishes genuinely lowers cost. Quality is maximised under the budget; cost is only a tie-breaker.
Feasibility is checked first with a min-cost solve: if even the cheapest varied plan is too expensive it allows repeats
(and warns); if that is still too expensive the cheapest plan is returned with `status: "over_budget"`, a clear warning
and suggestions. Dishes are then laid out across days so the same dish is not served back-to-back when avoidable.

## API

| Method | Path | Notes |
|---|---|---|
| POST | `/api/meal-plans/generate` | Body = plan request (below). Returns the full plan, also saved |
| GET | `/api/meal-plans` | Your saved plan summaries (header `X-User-Id`) |
| GET | `/api/meal-plans/{id}` | A saved plan |
| GET | `/api/meal-plans/{id}/shopping-list?format=json\|csv` | Consolidated list; `csv` downloads |
| POST | `/api/meal-plans/{id}/feedback` | `{recipe_id, rating: like\|dislike\|cook_again}` |
| GET | `/api/feedback` | Your ratings |
| GET | `/api/recipes/{id}?servings=N&currency=USD&price_level=1` | Scaled ingredients, cost, nutrition, method |
| GET | `/api/meta` | Cuisines, currencies, equipment, ingredient list |

Plan request fields: `budget`, `currency`, `food_preference` (vegetarian, non_vegetarian, vegan), `nutrition_goal`
(balanced, high_protein, high_fiber, weight_management), `days` 1-30, `people` 1-20, `cuisine` (or `any`),
`meals_per_day` 2/3/4, `allergies[]`, `dislikes[]`, `available_ingredients[{name, grams?}]`, `max_cook_time`
(quick, moderate, long), `equipment[]`, `price_level`, `price_overrides{ingredient_id: local price per kg}`,
`round_to_packs`, `max_repeats`, `seed`. Errors: 422 with `detail.errors` (or field errors), 404, 400.
"Users" are an anonymous `X-User-Id` string generated by the browser; there are no accounts or secrets.

## Dataset provenance and honesty

* Recipes are **starter recipes written for this project**; quantities are approximate and not copied from a source.
* Nutrition values are approximate per-100 g figures entered from general knowledge. **Verify them against a
  food-composition database (USDA FoodData Central, IFCT, CoFID, ...) before relying on them.**
* Prices (USD/kg) are **indicative placeholders**, and exchange rates are static. They are not live market prices.
  Use `price_level` or `price_overrides`, or edit `ingredients.csv`, to localise.
* Nutrition targets are generic references, scaled to the meals chosen. Not medical advice; no outcome is promised.

## Expanding the data

Add ingredient rows and recipes (grams per serving), run `pytest`. The loader validates everything. A "worldwide" app
needs worldwide data: the biggest gaps are more recipes per cuisine, regional ingredients, real regional prices and a
verified nutrition source.

## Deployment

Single container: `docker build -t dietwise . && docker run -p 8000:8000 -v dietwise-data:/data dietwise`
(open http://localhost:8000). Or deploy the backend (any host that runs `uvicorn app.main:app`) and the frontend
(`npm run build`, upload `dist/` to any static host; set `VITE_API_BASE` to the API URL at build time and
`CORS_ORIGINS` on the backend). SQLite is fine for one instance; move to PostgreSQL for several (only `app/db.py`
touches the database).

## Known limitations

* Only 63 recipes: with long plans or tight filters (vegan + allergies) dishes must repeat. The plan explains why.
* Latency: typical plans take under 2 s. Very tight budgets for 1 person over many days make the optimizer work harder (each solve is capped at `SOLVER_TIME_LIMIT`, 5 s, and the best feasible plan found is used), so those can take 10-15 s.
* No food photos, no metric/imperial toggle (quantities are in grams), English only.
* Dry beans/lentils are priced and measured dry; recipes say to soak and boil first.
* Allergy matching is conservative keyword + tag matching; unknown terms produce a warning. Always check labels.
* No labelled data exists, so Precision@K is not reported (see `python -m app.ml.evaluate` for what is measured).
