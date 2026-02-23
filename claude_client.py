"""Shared Claude CLI wrapper used by meal_planner and meal_regenerator."""

import json
import logging
import os
import subprocess
import threading
from pathlib import Path

from config import (
    CLAUDE_BIN,
    CLAUDE_MAX_BUDGET_USD,
    CLAUDE_MCP_CONFIG,
    CLAUDE_TIMEOUT_SECONDS,
    NUM_MEALS,
    NUM_NOTION_MEALS,
    NUM_WEB_MEALS,
)
from prompt_template import JSON_SCHEMA

log = logging.getLogger(__name__)


def get_claude_env() -> dict:
    """Build environment dict with PATH entries needed by Claude CLI and Notion MCP."""
    env = os.environ.copy()
    required_paths = [
        str(Path.home() / ".local" / "bin"),
        "/opt/homebrew/bin",
        "/opt/homebrew/sbin",
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
        "/usr/sbin",
        "/sbin",
    ]
    existing = env.get("PATH", "").split(":")
    for p in reversed(required_paths):
        if p not in existing:
            existing.insert(0, p)
    env["PATH"] = ":".join(existing)
    # Remove CLAUDECODE env var so the subprocess doesn't think it's nested
    env.pop("CLAUDECODE", None)
    return env


def call_claude(prompt: str) -> dict:
    """Call Claude CLI and return parsed structured output."""
    cmd = [
        str(CLAUDE_BIN),
        "-p",
        "--output-format", "json",
        "--json-schema", json.dumps(JSON_SCHEMA),
        "--permission-mode", "bypassPermissions",
        "--no-session-persistence",
        "--max-budget-usd", CLAUDE_MAX_BUDGET_USD,
        "--mcp-config", str(CLAUDE_MCP_CONFIG),
        prompt,
    ]

    log.info("Calling Claude CLI...")

    stderr_lines = []

    def stream_stderr(pipe):
        for line in iter(pipe.readline, ""):
            line = line.rstrip()
            if line:
                log.info(f"[claude] {line}")
                stderr_lines.append(line)
        pipe.close()

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        env=get_claude_env(),
    )

    t_err = threading.Thread(target=stream_stderr, args=(proc.stderr,), daemon=True)
    t_err.start()

    try:
        stdout_text, _ = proc.communicate(timeout=CLAUDE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        proc.kill()
        t_err.join(timeout=5)
        log.error(f"Claude CLI stderr before timeout: {' | '.join(stderr_lines)[:500]!r}")
        raise

    t_err.join(timeout=5)

    if proc.returncode != 0:
        raise RuntimeError(
            f"Claude CLI exited with code {proc.returncode}\n"
            f"stderr: {' '.join(stderr_lines)[:500]}"
        )

    response = json.loads(stdout_text)

    # Claude CLI >=2.1 moved structured output under the "result" key
    structured = response.get("structured_output")
    if structured is None:
        raw_result = response.get("result", "")
        # Try to parse the result field as JSON (structured output may be inline)
        if isinstance(raw_result, dict):
            structured = raw_result
        elif isinstance(raw_result, str) and raw_result.strip():
            try:
                structured = json.loads(raw_result)
            except json.JSONDecodeError:
                pass

    if structured is None:
        # Log the full response for debugging
        log.error(f"Full Claude response: {json.dumps(response, indent=2)[:2000]}")
        raise RuntimeError(
            f"No structured_output in Claude response. "
            f"Keys: {list(response.keys())}"
        )

    return structured


def validate_meals(meals: list) -> list:
    """Validate meal selections and warn on unexpected counts."""
    notion = [m for m in meals if m.get("source") == "notion"]
    web = [m for m in meals if m.get("source") == "web"]

    if len(meals) != NUM_MEALS:
        log.warning(f"Expected {NUM_MEALS} total meals, got {len(meals)}")
    if len(notion) != NUM_NOTION_MEALS:
        log.warning(f"Expected {NUM_NOTION_MEALS} Notion meals, got {len(notion)}")
    if len(web) != NUM_WEB_MEALS:
        log.warning(f"Expected {NUM_WEB_MEALS} web meals, got {len(web)}")

    # Ensure all meals have required fields
    valid = []
    for meal in meals:
        if all(k in meal for k in ("recipe_name", "source", "url")):
            valid.append(meal)
        else:
            log.warning(f"Skipping meal with missing fields: {meal}")

    return valid
