BODY = {"budget": 60, "currency": "USD", "food_preference": "vegetarian", "nutrition_goal": "high_fiber",
        "days": 3, "people": 2, "seed": 1}
H = {"X-User-Id": "tester1"}


def test_health_and_meta(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    m = client.get("/api/meta").json()
    assert m["recipe_count"] >= 60 and any(c["code"] == "INR" for c in m["currencies"])


def test_generate_fetch_and_shopping_list(client):
    r = client.post("/api/meal-plans/generate", json=BODY, headers=H)
    assert r.status_code == 200, r.text
    plan = r.json()
    assert len(plan["days"]) == 3
    again = client.get(f"/api/meal-plans/{plan['id']}").json()
    assert again["id"] == plan["id"]
    sl = client.get(f"/api/meal-plans/{plan['id']}/shopping-list").json()
    assert sl["total_cost"] == plan["shopping_list"]["total_cost"]
    csv = client.get(f"/api/meal-plans/{plan['id']}/shopping-list?format=csv")
    assert csv.headers["content-type"].startswith("text/csv") and "TOTAL" in csv.text
    assert plan["id"] in [p["id"] for p in client.get("/api/meal-plans", headers=H).json()]


def test_invalid_inputs(client):
    assert client.post("/api/meal-plans/generate", json={**BODY, "days": 31}).status_code == 422
    assert client.post("/api/meal-plans/generate", json={**BODY, "budget": -5}).status_code == 422
    assert client.post("/api/meal-plans/generate", json={**BODY, "food_preference": "carnivore"}).status_code == 422
    assert client.post("/api/meal-plans/generate", json={**BODY, "currency": "XYZ"}).status_code == 422
    assert client.post("/api/meal-plans/generate", json={**BODY, "cuisine": "martian"}).status_code == 422
    assert client.post("/api/meal-plans/generate", json={**BODY, "equipment": ["jetpack"]}).status_code == 422
    assert client.get("/api/meal-plans/doesnotexist").status_code == 404
    assert client.get("/api/recipes/nope").status_code == 404
    assert client.get("/api/meal-plans", headers={"X-User-Id": "bad id!"}).status_code == 400


def test_recipe_scaling(client):
    one = client.get("/api/recipes/dal_tadka_rice?servings=1").json()
    four = client.get("/api/recipes/dal_tadka_rice?servings=4").json()
    for a, b in zip(one["ingredients"], four["ingredients"]):
        assert b["grams_total"] == round(a["grams_total"] * 4, 2)
    assert four["estimated_cost"] == round(one["estimated_cost"] * 4, 2) or abs(four["estimated_cost"] - 4 * one["estimated_cost"]) < 0.05
    assert four["nutrition_total"]["kcal"] == round(one["nutrition_per_serving"]["kcal"] * 4, 1)


def test_feedback_is_stored_and_used(client):
    plan = client.post("/api/meal-plans/generate", json={**BODY, "days": 1, "meals_per_day": 2, "budget": 100}, headers=H).json()
    rid = plan["days"][0]["meals"][0]["recipe_id"]
    assert client.post(f"/api/meal-plans/{plan['id']}/feedback", json={"recipe_id": rid, "rating": "dislike"}, headers=H).status_code == 200
    assert client.get("/api/feedback", headers=H).json()[rid] == "dislike"
    nxt = client.post("/api/meal-plans/generate", json={**BODY, "days": 1, "meals_per_day": 2, "budget": 100}, headers=H).json()
    assert rid not in [m["recipe_id"] for m in nxt["days"][0]["meals"]]
    assert client.post(f"/api/meal-plans/{plan['id']}/feedback", json={"recipe_id": rid, "rating": "meh"}, headers=H).status_code == 422
    assert client.post(f"/api/meal-plans/{plan['id']}/feedback", json={"recipe_id": "nope", "rating": "like"}, headers=H).status_code == 404


def test_unfulfillable_request_returns_422_with_reasons(client):
    r = client.post("/api/meal-plans/generate", json={**BODY, "equipment": [], "allergies": ["chickpeas"], "meals_per_day": 3})
    assert r.status_code == 422 and r.json()["detail"]["errors"]
