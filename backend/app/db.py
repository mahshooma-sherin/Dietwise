"""SQLite persistence: saved plans and per-user meal feedback."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config


@contextmanager
def conn():
    c = sqlite3.connect(config.DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db() -> None:
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS plans (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, created_at TEXT NOT NULL, plan_json TEXT NOT NULL, is_saved INTEGER DEFAULT 0);
        CREATE INDEX IF NOT EXISTS idx_plans_user ON plans(user_id, created_at);
        CREATE TABLE IF NOT EXISTS feedback (
            user_id TEXT NOT NULL, recipe_id TEXT NOT NULL, rating TEXT NOT NULL, updated_at TEXT NOT NULL,
            PRIMARY KEY (user_id, recipe_id));
        """)
        try:
            c.execute("ALTER TABLE plans ADD COLUMN is_saved INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass


def save_plan(user_id: str, plan: dict, is_saved: bool = False) -> None:
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO plans (id, user_id, created_at, plan_json, is_saved) VALUES (?,?,?,?,?)",
                  (plan["id"], user_id, plan["created_at"], json.dumps(plan), 1 if is_saved else 0))


def mark_saved(user_id: str, plan_id: str, is_saved: bool = True) -> None:
    with conn() as c:
        c.execute("UPDATE plans SET is_saved=? WHERE id=? AND user_id=?",
                  (1 if is_saved else 0, plan_id, user_id))


def get_plan(plan_id: str):
    with conn() as c:
        row = c.execute("SELECT plan_json, is_saved FROM plans WHERE id=?", (plan_id,)).fetchone()
    if not row:
        return None
    p = json.loads(row["plan_json"])
    p["is_saved"] = bool(row["is_saved"]) if "is_saved" in row.keys() else False
    return p


def list_plans(user_id: str, limit: int = 50, saved_only: bool = False) -> list:
    with conn() as c:
        query = "SELECT plan_json, is_saved FROM plans WHERE user_id=? "
        if saved_only:
            query += "AND is_saved=1 "
        query += "ORDER BY created_at DESC LIMIT ?"
        rows = c.execute(query, (user_id, limit)).fetchall()
    out = []
    for r in rows:
        p = json.loads(r["plan_json"])
        req = p["request"]
        is_saved = bool(r["is_saved"]) if "is_saved" in r.keys() else False
        out.append({"id": p["id"], "created_at": p["created_at"], "status": p["status"], "days": req["days"],
                    "people": req["people"], "budget": req["budget"], "currency": p["currency"],
                    "food_preference": req["food_preference"], "nutrition_goal": req["nutrition_goal"],
                    "grocery_total": p["summary"]["grocery_total"], "is_saved": is_saved})
    return out


def upsert_feedback(user_id: str, recipe_id: str, rating: str) -> None:
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO feedback VALUES (?,?,?,?)",
                  (user_id, recipe_id, rating, datetime.now(timezone.utc).isoformat(timespec="seconds")))


def get_feedback(user_id: str) -> dict:
    with conn() as c:
        rows = c.execute("SELECT recipe_id, rating FROM feedback WHERE user_id=?", (user_id,)).fetchall()
    return {r["recipe_id"]: r["rating"] for r in rows}
