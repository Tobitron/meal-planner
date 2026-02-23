"""Prompt template and JSON schema for Claude CLI meal selection."""

from config import NUM_MEALS, NUM_NOTION_MEALS, NUM_WEB_MEALS

# ============================================================================
# Notion recipe sources
# ============================================================================
NOTION_SOURCES = {
    "Meal Prep Options Table": "https://www.notion.so/7eecd65aebe2482d9993f0d9ba8482cb",
    "Dense Bean Salads": "https://www.notion.so/474472b92e9f425484729fcee54b4e2c",
}

# ============================================================================
# Selection rules
# ============================================================================
USER_SELECTION_RULES = """\
You are a weekly meal prep planner. Search my Notion workspace for recipes and \
select {num_meals} meals for the upcoming week.

## Sources
Search these two Notion pages for recipes:
1. "Meal Prep Options Table" (database) - Only select recipes where "Is it good?" is "Yes" or "TBD". Do NOT select recipes where "Is it good?" is "No".
2. "Dense Bean Salads" (page with subpages) - Each subpage is a recipe.

## Meal Split
- {num_notion} meals from Notion (from either of the two sources above)
- {num_web} meal from a web search (find a recipe online that fits all the rules below)

## Diet Rules (Mediterranean Diet)
All meals must follow Mediterranean diet guidelines. This does NOT mean meals must \
literally be from the Mediterranean region — it means they follow the diet principles:
- **No red meat.** Acceptable proteins: fish, poultry, eggs, beans/legumes, tofu.
- **Full-fat dairy** can be a minor component in all meals, but may only be a \
major component in at most 1 meal per week.
- **Rice** can be used in a maximum of 2 meals per week.
- Emphasize vegetables, whole grains, legumes, healthy fats (olive oil, nuts).

## Weekly Requirements
- Every week must include exactly **1 bean-based meal** (e.g., lentil soup, chili, \
bean stew — NOT counting dense bean salads).
- Every week must include exactly **1 salad bowl** (a dense bean salad counts).
- The remaining 2 meals are flexible (any type that follows diet rules).

## Portion Size
All meals must make **at least 4 servings**, ideally 6. Prefer recipes that scale \
easily to 6 servings.

## Cooking Style Preferences
Prioritize meals that:
- Can be made easily in bulk
- Minimize dish washing (one-pot meals, sheet-pan meals, Instant Pot, dump-and-bake)
- Are freezable when possible
- Use frozen or pre-cut vegetables when practical

## Output
Respond with ONLY a JSON object in this exact format, no other text:
{
  "meals": [
    {
      "recipe_name": "exact recipe name",
      "source": "notion" or "web",
      "url": "notion page URL or web recipe URL"
    }
  ]
}
"""

# JSON schema for Claude CLI --json-schema structured output
JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "meals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "recipe_name": {
                        "type": "string",
                        "description": "Exact recipe name",
                    },
                    "source": {
                        "type": "string",
                        "enum": ["notion", "web"],
                        "description": "Whether recipe is from Notion or web search",
                    },
                    "url": {
                        "type": "string",
                        "description": "Notion page URL or web recipe URL",
                    },
                },
                "required": ["recipe_name", "source", "url"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["meals"],
    "additionalProperties": False,
}


def build_regeneration_prompt(current_meals: list, feedback: str, excluded_recipes: list) -> str:
    """Build a prompt for revising an existing meal plan based on user feedback."""
    # Format current meal list
    meal_lines = []
    for i, meal in enumerate(current_meals, 1):
        meal_lines.append(
            f'{i}. {meal["recipe_name"]} ({meal["source"]}) — {meal.get("url", "")}'
        )
    current_plan = "\n".join(meal_lines)

    prompt = (
        "You are revising a weekly meal prep plan based on user feedback.\n\n"
        "## Current Meal Plan\n"
        f"{current_plan}\n\n"
        "## User Feedback\n"
        f'"{feedback}"\n\n'
        "## Instructions\n"
        "- Keep meals the user is happy with\n"
        "- Replace only the meals the user wants changed\n"
        f"- Follow the same diet rules and source split ({NUM_NOTION_MEALS} Notion, {NUM_WEB_MEALS} web)\n"
        "- Still avoid recently-used recipes (exclusion list below)\n"
        "- Search my Notion workspace for replacement Notion recipes\n"
        "- Use a web search for replacement web recipes\n"
        f"- Return exactly {NUM_MEALS} meals total\n"
    )

    if excluded_recipes:
        prompt += (
            "\n## Exclusions\n"
            "DO NOT select any of the following recipes "
            "(they were chosen in the last few weeks):\n"
        )
        for name in excluded_recipes:
            prompt += f"- {name}\n"

    return prompt


def build_prompt(excluded_recipes: list, ingredient_hints: list = None) -> str:
    """Build the full prompt with user rules, exclusion list, and ingredient hints."""
    rules = USER_SELECTION_RULES.format(
        num_meals=NUM_MEALS,
        num_notion=NUM_NOTION_MEALS,
        num_web=NUM_WEB_MEALS,
    )

    if excluded_recipes:
        exclusion_block = (
            "\n\n## Exclusions\n"
            "DO NOT select any of the following recipes "
            "(they were chosen in the last few weeks):\n"
        )
        for name in excluded_recipes:
            exclusion_block += f"- {name}\n"
    else:
        exclusion_block = ""

    if ingredient_hints:
        hints_block = (
            "\n\n## Ingredient Requests\n"
            "Try to incorporate these ingredients into at least one recipe this week:\n"
        )
        for hint in ingredient_hints:
            hints_block += f'- "{hint}"\n'
    else:
        hints_block = ""

    return rules + exclusion_block + hints_block
