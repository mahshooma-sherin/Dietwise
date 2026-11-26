"""Central configuration. Everything tunable lives here or in environment variables."""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / ".env")

DATA_DIR = Path(os.getenv("DIETWISE_DATA_DIR", BASE_DIR / "data"))
DB_PATH = os.getenv("DIETWISE_DB", str(BASE_DIR / "dietwise.db"))
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]

# Recommender: weights of each score component (see ml/recommender.py)
WEIGHTS = {"similarity": 0.30, "goal": 0.30, "time": 0.05, "cost": 0.10, "pantry": 0.10, "cuisine": 0.25}
FEEDBACK_BOOST = {"like": 0.15, "cook_again": 0.30}
DISLIKE_SIMILARITY_PENALTY = 0.30

# Variety (MMR): 1.0 = pure relevance, 0.0 = pure diversity
MMR_LAMBDA = 0.7
# Optimizer objective weights
REPEAT_PENALTY = 0.6   # score lost for each repeat of the same dish
# Budget is a hard constraint (exact shopping bill), so cost is only a tie-breaker in the objective
COST_WEIGHT = 0.2
# Controlled randomness: each recipe score gets +uniform(0, RANDOMNESS) so new plans differ (seeded when a seed is given)
RANDOMNESS = 0.08
# Recipe-to-recipe similarity used for variety = mix of ingredient TF-IDF cosine and "same cuisine/staple/protein"
SIMILARITY_MIX = {"tfidf": 0.4, "cuisine": 0.2, "staple": 0.2, "protein": 0.2}
SOLVER_TIME_LIMIT = 5  # seconds per solve; the best feasible plan found is used

TIME_CAPS = {"quick": 25, "moderate": 45, "long": None}
MEAL_SLOTS = {
    2: ["lunch", "dinner"],
    3: ["breakfast", "lunch", "dinner"],
    4: ["breakfast", "lunch", "dinner", "snack"],
}
SLOT_TYPE = {"breakfast": "breakfast", "lunch": "main", "dinner": "main", "snack": "snack"}
# Share of a day's energy/nutrients each slot is assumed to cover (used to scale reference targets)
SLOT_SHARE = {"breakfast": 0.25, "lunch": 0.35, "dinner": 0.30, "snack": 0.10}

# Generic reference values per person per day. NOT medical advice; edit freely.
REFERENCE_TARGETS = {
    "balanced": {"kcal": 2000, "protein": 50, "carbs": 260, "fat": 65, "fiber": 28},
    "high_protein": {"kcal": 2000, "protein": 80, "carbs": 220, "fat": 65, "fiber": 28},
    "high_fiber": {"kcal": 2000, "protein": 50, "carbs": 260, "fat": 65, "fiber": 35},
    "weight_management": {"kcal": 1800, "protein": 65, "carbs": 210, "fat": 55, "fiber": 30},
}
EQUIPMENT = ["stovetop", "oven", "pressure_cooker", "air_fryer", "microwave", "blender"]
