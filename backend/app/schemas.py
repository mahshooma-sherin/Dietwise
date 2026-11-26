from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class PantryItem(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    grams: Optional[float] = Field(default=None, gt=0, le=1_000_000)  # None = "I have plenty"


class PlanRequest(BaseModel):
    budget: float = Field(gt=0, le=1e9)
    currency: str = "USD"
    food_preference: Literal["vegetarian", "non_vegetarian", "vegan"]
    nutrition_goal: Literal["balanced", "high_protein", "high_fiber", "weight_management"]
    days: int = Field(ge=1, le=30)
    people: int = Field(ge=1, le=20)
    cuisine: str = "any"
    meals_per_day: Literal[2, 3, 4] = 3
    allergies: list[str] = Field(default_factory=list, max_length=30)
    dislikes: list[str] = Field(default_factory=list, max_length=30)
    available_ingredients: list[PantryItem] = Field(default_factory=list, max_length=60)
    max_cook_time: Literal["quick", "moderate", "long"] = "long"
    equipment: list[str] = Field(default_factory=lambda: ["stovetop"])
    price_level: float = Field(default=1.0, gt=0.05, le=10)
    price_overrides: dict[str, float] = Field(default_factory=dict)  # ingredient id -> local price per kg
    round_to_packs: bool = True
    allow_repeats_for_budget: bool = False  # False = keep variety even if the plan then exceeds the budget
    max_repeats: int = Field(default=1, ge=1, le=5)
    seed: Optional[int] = None

    @field_validator("allergies", "dislikes")
    @classmethod
    def _clean(cls, v):
        return [t.strip() for t in v if t and t.strip()]

    @field_validator("cuisine", "currency")
    @classmethod
    def _norm(cls, v):
        return v.strip()


class FeedbackIn(BaseModel):
    recipe_id: str
    rating: Literal["like", "dislike", "cook_again"]
