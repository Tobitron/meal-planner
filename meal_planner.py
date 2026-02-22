#!/usr/bin/env python3
"""Weekly meal planner orchestrator.

Calls Claude CLI with Notion MCP to select meals, saves to CSV, and emails the plan.
"""

import logging
import socket
import subprocess
import sys
from datetime import datetime

from config import (
    CLAUDE_TIMEOUT_SECONDS,
    LOG_DIR,
)
from claude_client import call_claude, validate_meals
from csv_history import append_meal_plan, read_recent_recipes
from email_sender import send_failure_email, send_meal_plan_email
from prompt_template import build_prompt

# Set up logging
LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / f"meal_planner_{datetime.now():%Y%m%d_%H%M%S}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def main() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    log.info(f"Starting meal planner for {today}")

    try:
        # 1. Read recent history
        excluded = read_recent_recipes()
        log.info(f"Excluding {len(excluded)} recipes from last 6 weeks")

        # 1.5. Check ingredient request emails (non-fatal)
        ingredient_hints = []
        try:
            from email_reader import fetch_ingredient_requests
            ingredient_hints = fetch_ingredient_requests()
            if ingredient_hints:
                log.info(f"Ingredient requests: {ingredient_hints}")
        except Exception as e:
            log.warning(f"Could not read ingredient emails: {e}")

        # 2. Build prompt
        prompt = build_prompt(excluded, ingredient_hints)
        log.info(f"Prompt length: {len(prompt)} chars")

        # 3. Check network before calling Claude
        try:
            socket.setdefaulttimeout(5)
            socket.getaddrinfo("api.anthropic.com", 443)
            log.info("Network check passed: api.anthropic.com is reachable")
        except OSError as e:
            log.error(f"Network check failed before Claude CLI call: {e}")
            raise RuntimeError(f"No network connectivity to api.anthropic.com: {e}")

        # 4. Call Claude CLI
        structured = call_claude(prompt)
        meals = structured.get("meals", [])
        log.info(f"Claude returned {len(meals)} meals")

        # 5. Validate
        meals = validate_meals(meals)
        if not meals:
            raise RuntimeError("No valid meals returned from Claude")

        # 6. Save to CSV
        append_meal_plan(meals, today)
        log.info(f"Saved {len(meals)} meals to CSV")

        # 7. Send email
        send_meal_plan_email(meals, today)
        log.info("Meal plan email sent successfully")

    except subprocess.TimeoutExpired:
        error = f"Claude CLI timed out after {CLAUDE_TIMEOUT_SECONDS}s"
        log.error(error)
        _try_failure_email(error)
        sys.exit(1)

    except Exception as e:
        log.error(f"Meal planner failed: {e}", exc_info=True)
        _try_failure_email(str(e))
        sys.exit(1)

    log.info("Meal planner completed successfully")


def _try_failure_email(error: str) -> None:
    """Attempt to send failure notification; don't crash if email also fails."""
    try:
        send_failure_email(error)
        log.info("Failure notification email sent")
    except Exception as email_err:
        log.error(f"Could not send failure email: {email_err}")


if __name__ == "__main__":
    main()
