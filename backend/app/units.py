"""Unit conversion and quantity formatting. Internally everything is grams (1 ml ~ 1 g)."""
import math

UNIT_TO_G = {
    "g": 1.0, "gram": 1.0, "grams": 1.0, "kg": 1000.0, "kilogram": 1000.0, "mg": 0.001,
    "oz": 28.3495, "ounce": 28.3495, "lb": 453.592, "lbs": 453.592, "pound": 453.592,
    "ml": 1.0, "l": 1000.0, "litre": 1000.0, "liter": 1000.0,
}


def to_grams(value: float, unit: str, piece_g: float | None = None) -> float:
    u = unit.strip().lower()
    if u in ("pc", "pcs", "piece", "pieces"):
        if not piece_g:
            raise ValueError("This ingredient has no piece weight, so pieces cannot be converted")
        return value * piece_g
    if u not in UNIT_TO_G:
        raise ValueError(f"Unknown unit: {unit}")
    return value * UNIT_TO_G[u]


def round_up_to_pack(grams: float, pack_g: float) -> float:
    if grams <= 1e-9:
        return 0.0
    return math.ceil(grams / pack_g - 1e-9) * pack_g


def format_qty(grams: float, piece_g: float | None = None) -> str:
    if grams >= 1000:
        s = f"{grams / 1000:.2f}".rstrip("0").rstrip(".") + " kg"
    elif grams >= 10 or abs(grams - round(grams)) < 1e-9:
        s = f"{grams:.0f} g"
    else:
        s = f"{grams:.1f} g"
    if piece_g and grams / piece_g >= 0.75:
        s += f" (about {round(grams / piece_g)} pcs)"
    return s
