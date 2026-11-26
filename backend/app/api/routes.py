from __future__ import annotations

import re

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import Response

from .. import config, db
from ..data_loader import CUISINE_LABELS, get_store
from ..schemas import FeedbackIn, PlanRequest
from ..services.grocery import shopping_list_csv
from ..services.planner import PlanInputError, generate_plan
from ..services.recipes import recipe_detail

router = APIRouter()
_UID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _user(x_user_id: str | None) -> str:
    if x_user_id is None:
        return "anonymous"
    if not _UID.match(x_user_id):
        raise HTTPException(400, "X-User-Id must be 1-64 characters: letters, digits, '-' or '_'.")
    return x_user_id


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/meta")
def meta():
    s = get_store()
    return {
        "cuisines": [{"id": c, "label": CUISINE_LABELS.get(c, c)} for c in s.cuisines],
        "currencies": [{"code": k, "name": v["name"], "symbol": v["symbol"]} for k, v in s.currencies.items()],
        "equipment": config.EQUIPMENT,
        "ingredients": [{"id": i.id, "name": i.name} for i in s.ingredients.values()],
        "recipe_count": len(s.recipes),
        "currency_note": "Exchange rates and prices in the starter data are static, indicative values.",
    }


@router.post("/meal-plans/generate")
def generate(req: PlanRequest, x_user_id: str | None = Header(default=None)):
    uid = _user(x_user_id)
    try:
        plan = generate_plan(req, feedback=db.get_feedback(uid))
    except PlanInputError as e:
        raise HTTPException(422, {"message": "Could not build a plan.", "errors": e.errors})
    db.save_plan(uid, plan, is_saved=False)
    return plan


@router.get("/meal-plans")
def list_plans(saved: bool = False, x_user_id: str | None = Header(default=None)):
    return db.list_plans(_user(x_user_id), saved_only=saved)


@router.post("/meal-plans/{plan_id}/save")
def save_plan_endpoint(plan_id: str, x_user_id: str | None = Header(default=None)):
    uid = _user(x_user_id)
    plan = db.get_plan(plan_id)
    if not plan:
        raise HTTPException(404, "Meal plan not found.")
    db.mark_saved(uid, plan_id, is_saved=True)
    return {"status": "saved", "id": plan_id}


@router.delete("/meal-plans/{plan_id}/save")
def unsave_plan_endpoint(plan_id: str, x_user_id: str | None = Header(default=None)):
    uid = _user(x_user_id)
    plan = db.get_plan(plan_id)
    if not plan:
        raise HTTPException(404, "Meal plan not found.")
    db.mark_saved(uid, plan_id, is_saved=False)
    return {"status": "unsaved", "id": plan_id}


@router.get("/meal-plans/{plan_id}")
def get_plan(plan_id: str):
    plan = db.get_plan(plan_id)
    if not plan:
        raise HTTPException(404, "Meal plan not found.")
    return plan


@router.get("/meal-plans/{plan_id}/shopping-list")
def shopping_list(plan_id: str, format: str = Query("json", pattern="^(json|csv)$")):
    plan = db.get_plan(plan_id)
    if not plan:
        raise HTTPException(404, "Meal plan not found.")
    if format == "csv":
        body = shopping_list_csv(plan["shopping_list"], plan["currency"]["code"])
        return Response(body, media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="shopping-list-{plan_id}.csv"'})
    return {"currency": plan["currency"], **plan["shopping_list"]}


@router.post("/meal-plans/{plan_id}/feedback")
def feedback(plan_id: str, body: FeedbackIn, x_user_id: str | None = Header(default=None)):
    uid = _user(x_user_id)
    plan = db.get_plan(plan_id)
    if not plan:
        raise HTTPException(404, "Meal plan not found.")
    if body.recipe_id not in get_store().recipe_by_id:
        raise HTTPException(404, "Recipe not found.")
    db.upsert_feedback(uid, body.recipe_id, body.rating)
    return {"recipe_id": body.recipe_id, "rating": body.rating}


@router.get("/feedback")
def my_feedback(x_user_id: str | None = Header(default=None)):
    return db.get_feedback(_user(x_user_id))


@router.get("/recipes/{recipe_id}")
def recipe(recipe_id: str, servings: int = Query(1, ge=1, le=200), currency: str = "USD",
           price_level: float = Query(1.0, gt=0.05, le=10)):
    s = get_store()
    if recipe_id not in s.recipe_by_id:
        raise HTTPException(404, "Recipe not found.")
    if currency not in s.currencies:
        raise HTTPException(422, f"Unsupported currency '{currency}'.")
    return recipe_detail(s, recipe_id, servings, currency, price_level)
