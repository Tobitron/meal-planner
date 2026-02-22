"""CSV history tracking for meal plan selections."""

import csv
from datetime import datetime, timedelta
from typing import Optional

from config import CSV_PATH, EXCLUSION_WEEKS

CSV_HEADER = ["date", "source", "recipe_name", "url"]


def read_recent_recipes(weeks: int = EXCLUSION_WEEKS) -> list:
    """Return recipe names selected within the last `weeks` weeks."""
    if not CSV_PATH.exists():
        return []

    cutoff = datetime.now() - timedelta(weeks=weeks)
    recent = []

    with open(CSV_PATH, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                row_date = datetime.strptime(row["date"], "%Y-%m-%d")
            except (ValueError, KeyError):
                continue
            if row_date >= cutoff:
                recent.append(row["recipe_name"])

    return recent


def get_latest_meal_plan(date: str) -> list[dict]:
    """Read all meal rows for a specific date. Returns list of meal dicts."""
    if not CSV_PATH.exists():
        return []

    meals = []
    with open(CSV_PATH, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("date") == date:
                meals.append(dict(row))

    return meals


def overwrite_meal_plan(meals: list, date: str) -> None:
    """Rewrite CSV, replacing all rows for `date` with new meals."""
    if not CSV_PATH.exists():
        return

    # Read all existing rows
    with open(CSV_PATH, newline="") as f:
        reader = csv.DictReader(f)
        rows = [row for row in reader if row.get("date") != date]

    # Write back with header, preserved rows, and new meals
    with open(CSV_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        for meal in meals:
            writer.writerow({
                "date": date,
                "source": meal["source"],
                "recipe_name": meal["recipe_name"],
                "url": meal.get("url", ""),
            })


def append_meal_plan(meals: list, date: Optional[str] = None) -> None:
    """Append meal selections to the CSV.

    Each meal dict should have: recipe_name, source, url
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    file_exists = CSV_PATH.exists()

    with open(CSV_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        if not file_exists:
            writer.writeheader()
        for meal in meals:
            writer.writerow({
                "date": date,
                "source": meal["source"],
                "recipe_name": meal["recipe_name"],
                "url": meal.get("url", ""),
            })
