#!/usr/bin/env python3
"""Meal plan regeneration based on email replies.

Intended to run every 15-30 min via cron. Detects replies to the meal plan
email, regenerates the plan using Claude, overwrites the CSV, and sends
a revised email.
"""

import csv
import logging
import subprocess
import sys
from datetime import datetime
from typing import Optional

from config import (
    CLAUDE_TIMEOUT_SECONDS,
    CSV_PATH,
    LOG_DIR,
)
from claude_client import call_claude, validate_meals
from csv_history import get_latest_meal_plan, overwrite_meal_plan, read_recent_recipes
from email_reader import fetch_meal_plan_replies
from email_sender import send_revised_meal_plan_email
from prompt_template import build_regeneration_prompt

# Set up logging
LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / f"meal_regenerator_{datetime.now():%Y%m%d_%H%M%S}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def get_most_recent_date() -> Optional[str]:
    """Find the most recent date in the meal history CSV."""
    if not CSV_PATH.exists():
        return None

    latest = None
    with open(CSV_PATH, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_str = row.get("date")
            if not date_str:
                continue
            try:
                row_date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue
            if latest is None or row_date > latest:
                latest = row_date

    return latest.strftime("%Y-%m-%d") if latest else None


def main() -> None:
    log.info("Checking for meal plan replies...")

    try:
        # 1. Check for replies
        replies = fetch_meal_plan_replies()
        if not replies:
            log.info("No unread meal plan replies found, exiting")
            return

        log.info(f"Found {len(replies)} reply(ies)")

        # 2. Determine date of most recent meal plan
        date = get_most_recent_date()
        if not date:
            log.warning("No meal history found in CSV, cannot regenerate")
            return

        # 3. Load current meals for that date
        current_meals = get_latest_meal_plan(date)
        if not current_meals:
            log.warning(f"No meals found for date {date}, cannot regenerate")
            return

        log.info(f"Loaded {len(current_meals)} meals for {date}")

        # 4. Load exclusion list
        excluded = read_recent_recipes()
        log.info(f"Excluding {len(excluded)} recently-used recipes")

        # 5. Combine all feedback into one string
        feedback = "\n\n".join(replies)
        log.info(f"Combined feedback ({len(feedback)} chars): {feedback[:200]!r}")

        # 6. Build regeneration prompt
        prompt = build_regeneration_prompt(current_meals, feedback, excluded)
        log.info(f"Prompt length: {len(prompt)} chars")

        # 7. Call Claude
        structured = call_claude(prompt)
        meals = structured.get("meals", [])
        log.info(f"Claude returned {len(meals)} meals")

        # 8. Validate
        meals = validate_meals(meals)
        if not meals:
            log.error("No valid meals returned from Claude, aborting")
            return

        # 9. Overwrite CSV
        overwrite_meal_plan(meals, date)
        log.info(f"Overwrote meal plan for {date} in CSV")

        # 10. Send revised email
        send_revised_meal_plan_email(meals, date)
        log.info("Revised meal plan email sent successfully")

    except subprocess.TimeoutExpired:
        log.error(f"Claude CLI timed out after {CLAUDE_TIMEOUT_SECONDS}s")

    except Exception as e:
        log.error(f"Meal regeneration failed: {e}", exc_info=True)

    log.info("Meal regenerator finished")


if __name__ == "__main__":
    main()
