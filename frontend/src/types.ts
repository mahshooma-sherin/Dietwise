export type Nutrition = { kcal: number; protein: number; carbs: number; fat: number; fiber: number };

export interface Meta {
  cuisines: { id: string; label: string }[];
  currencies: { code: string; name: string; symbol: string }[];
  equipment: string[];
  ingredients: { id: string; name: string }[];
  recipe_count: number;
  currency_note: string;
}

export interface PlanRequest {
  budget: number;
  currency: string;
  food_preference: "vegetarian" | "non_vegetarian" | "vegan";
  nutrition_goal: "balanced" | "high_protein" | "high_fiber" | "weight_management";
  days: number;
  people: number;
  cuisine: string;
  meals_per_day: 2 | 3 | 4;
  allergies: string[];
  dislikes: string[];
  available_ingredients: { name: string; grams?: number }[];
  max_cook_time: "quick" | "moderate" | "long";
  equipment: string[];
  price_level: number;
  round_to_packs: boolean;
  allow_repeats_for_budget: boolean;
  max_repeats: number;
}

export interface Meal {
  slot: string;
  recipe_id: string;
  name: string;
  cuisine_label: string;
  description: string;
  time_min: number;
  servings: number;
  cost: number;
  cost_per_serving: number;
  nutrition: Nutrition | null;
  diet: string;
  allergens: string[];
  match_score: number;
  reasons: string[];
}

export interface Day {
  day: number;
  meals: Meal[];
  totals: { nutrition: Nutrition; cost: number };
}

export interface ShoppingItem {
  id: string;
  name: string;
  needed_g: number;
  needed_display: string;
  available_g: number | null;
  available_unlimited: boolean;
  to_buy_g: number;
  purchase_g: number;
  purchase_display: string;
  estimated_cost: number;
}

export interface ShoppingGroup {
  category: string;
  items: ShoppingItem[];
}

export interface Plan {
  id: string;
  created_at: string;
  status: "ok" | "over_budget";
  warnings: string[];
  suggestions: string[];
  notes: string[];
  currency: { code: string; symbol: string };
  request: PlanRequest;
  days: Day[];
  shopping_list: { groups: ShoppingGroup[]; total_cost: number; item_count: number };
  summary: {
    budget: number;
    grocery_total: number;
    budget_used_pct: number;
    meals_cost: number;
    total_servings: number;
    avg_cost_per_serving: number;
    distinct_dishes: number;
    total_meals: number;
    cuisine_match_pct: number | null;
    nutrition: {
      avg_per_person_day: Nutrition;
      reference_targets: Nutrition;
      percent_of_reference: Record<string, number | null>;
      meals_missing_nutrition_data: number;
      note: string;
    };
  };
}

export interface PlanSummary {
  id: string;
  created_at: string;
  status: string;
  days: number;
  people: number;
  budget: number;
  currency: { code: string; symbol: string };
  food_preference: string;
  nutrition_goal: string;
  grocery_total: number;
}

export interface RecipeDetail {
  id: string;
  name: string;
  cuisine_label: string;
  description: string;
  time_min: number;
  equipment: string[];
  diet: string;
  allergens: string[];
  servings: number;
  ingredients: { id: string; name: string; display: string; estimated_cost: number }[];
  steps: string[];
  source: string;
  currency: { code: string; symbol: string };
  estimated_cost: number;
  cost_per_serving: number;
  nutrition_per_serving: Nutrition | null;
  nutrition_total: Nutrition | null;
}

export type Rating = "like" | "dislike" | "cook_again";
