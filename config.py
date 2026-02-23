"""Configuration constants for the meal planner."""

from pathlib import Path

# Paths
PROJECT_DIR = Path(__file__).parent
CSV_PATH = PROJECT_DIR / "meal_history.csv"
LOG_DIR = PROJECT_DIR / "logs"
CLAUDE_BIN = Path.home() / ".local" / "bin" / "claude"

# Meal plan settings
NUM_MEALS = 4          # Total meals per week
NUM_NOTION_MEALS = 3   # Sourced from Notion
NUM_WEB_MEALS = 1      # Sourced from web search
EXCLUSION_WEEKS = 6

# Claude CLI settings
CLAUDE_TIMEOUT_SECONDS = 900  # 15 minutes for Notion search + web search
CLAUDE_MAX_BUDGET_USD = "1.00"
CLAUDE_MCP_CONFIG = PROJECT_DIR / "mcp_config.json"

# Email settings
GMAIL_SENDER = "tobykahn@gmail.com"
GMAIL_RECIPIENTS = ["tobiasbkahn@gmail.com"]
GMAIL_APP_PASSWORD_ENV = "MEAL_PLANNER_GMAIL_APP_PASSWORD"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

# IMAP settings (for reading ingredient request emails)
IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
GMAIL_INGREDIENT_KEYWORD = "use"
GMAIL_AUTHORIZED_SENDERS = [
    "tobiasbkahn@gmail.com",
    "mindynichamin@gmail.com",
    "tobykahn@gmail.com",
]
GMAIL_REPLY_SUBJECT_PREFIX = "Re: Meal"
