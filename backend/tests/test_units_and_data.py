import json
import shutil

import pytest

from app.data_loader import DataError, DataStore
from app.units import format_qty, round_up_to_pack, to_grams


def test_unit_conversion_equivalence():
    assert to_grams(0.5, "kg") == to_grams(500, "g") == 500
    assert to_grams(1, "lb") == pytest.approx(453.592)
    assert to_grams(3, "pcs", piece_g=50) == 150
    with pytest.raises(ValueError):
        to_grams(1, "pcs")
    with pytest.raises(ValueError):
        to_grams(1, "furlong")


def test_pack_rounding_and_format():
    assert round_up_to_pack(0, 500) == 0
    assert round_up_to_pack(1, 500) == 500
    assert round_up_to_pack(500, 500) == 500
    assert round_up_to_pack(501, 500) == 1000
    assert format_qty(1500) == "1.5 kg"
    assert "6 pcs" in format_qty(300, 50)


def test_dataset_is_consistent(store):
    assert len(store.recipes) >= 60
    for r in store.recipes:
        assert r.nutrition and r.nutrition["kcal"] > 50
        assert r.cost_usd and r.cost_usd > 0


def test_diet_and_allergens_are_derived(store):
    assert store.recipe_by_id["kerala_fish_curry_rice"].diet == "non_veg"
    assert store.recipe_by_id["egg_bhurji_toast"].diet == "vegetarian"
    assert store.recipe_by_id["dal_tadka_rice"].diet == "vegan"
    assert "peanut" in store.recipe_by_id["groundnut_stew_rice"].allergens


def test_unknown_ingredient_in_recipe_is_rejected(tmp_path):
    from app import config
    shutil.copytree(config.DATA_DIR, tmp_path / "d")
    recipes = json.loads((tmp_path / "d" / "recipes.json").read_text())
    recipes[0]["ingredients"]["unobtainium"] = 10
    (tmp_path / "d" / "recipes.json").write_text(json.dumps(recipes))
    with pytest.raises(DataError):
        DataStore(tmp_path / "d")


def test_missing_nutrition_and_price_are_flagged(tmp_path):
    from app import config
    shutil.copytree(config.DATA_DIR, tmp_path / "d")
    csv_path = tmp_path / "d" / "ingredients.csv"
    lines = csv_path.read_text().splitlines()
    lines = [l.replace("rice,Rice,Grains & cereals,360,7,79,0.6,1.3,1.6", "rice,Rice,Grains & cereals,,7,79,0.6,1.3,") if l.startswith("rice,") else l for l in lines]
    csv_path.write_text("\n".join(lines))
    s = DataStore(tmp_path / "d")
    r = s.recipe_by_id["dal_tadka_rice"]
    assert r.nutrition is None and r.cost_usd is None
