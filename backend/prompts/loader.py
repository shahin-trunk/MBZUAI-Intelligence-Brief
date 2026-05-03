import re
from pathlib import Path

from config import (
    PROMPTS_DIR,
    DELIVERY_FORMAT,
    USER_PROFILE,
    get_today_date,
    get_date_variable,
    get_lookback_cutoff_date,
    get_previous_brief,
    get_previous_brief_headlines,
    get_recent_history_headlines,
)


def extract_prompt_from_md(md_text: str) -> str:
    """Extract the prompt text from between ``` code fences in a markdown file.

    The prompt .md files wrap the actual prompt in a single ``` code block.
    This extracts just the prompt content, discarding markdown commentary.
    """
    # Match content between ``` fences (non-greedy, but we want the biggest block)
    matches = re.findall(r"```\n(.*?)```", md_text, re.DOTALL)
    if matches:
        # Return the longest match (the main prompt block)
        return max(matches, key=len).strip()
    # Fallback: return the whole text if no fences found
    return md_text.strip()


def load_prompt(
    prompt_filename: str,
    scout_output: str = "",
    gatekeeper_output: str = "",
    ghostwriter_output: str = "",
    items_json: str = "",
) -> str:
    """Load a prompt .md file, extract the prompt, and replace all template variables.

    Args:
        prompt_filename: Name of the .md file in the prompts directory.
        scout_output: Combined scout results JSON (for Gatekeeper).
        gatekeeper_output: Gatekeeper output JSON (for Ghostwriter and Editor).
        ghostwriter_output: Ghostwriter output JSON (for Editor).
        items_json: Items JSON (for Content Filter).

    Returns:
        The fully templated prompt string ready for the API call.
    """
    # Accept either a bare filename (resolved against PROMPTS_DIR) or an
    # absolute path / path-like string. The eval harness uses this to point
    # load_prompt at alternate-version prompt files without copying them into
    # PROMPTS_DIR.
    candidate = Path(prompt_filename)
    if candidate.is_absolute() or ("/" in prompt_filename or "\\" in prompt_filename):
        prompt_path = candidate
    else:
        prompt_path = PROMPTS_DIR / prompt_filename
    raw_md = prompt_path.read_text(encoding="utf-8")
    prompt_text = extract_prompt_from_md(raw_md)

    # `{previous_brief_headlines}` stays PUBLISHED-ONLY so the Gatekeeper
    # and Synthesis prompts don't balloon with the full pending-slate
    # history. `{recent_history}` is the merged published + pending view,
    # used by the dedicated history-dedup agent.
    replacements = {
        "{date_variable}": get_date_variable(),
        "{lookback_cutoff}": get_lookback_cutoff_date().strftime("%Y-%m-%d %H:%M %Z"),
        "{previous_brief_headlines}": get_previous_brief_headlines(),
        "{recent_history}": get_recent_history_headlines(),
        "{scout_output}": scout_output,
        "{gatekeeper_output}": gatekeeper_output,
        "{ghostwriter_output}": ghostwriter_output,
        "{items_json}": items_json,
        "{user_profile}": USER_PROFILE,
        "{delivery_format}": DELIVERY_FORMAT,
        "{date}": get_today_date(),
        "{previous_brief}": get_previous_brief(),
    }

    for placeholder, value in replacements.items():
        prompt_text = prompt_text.replace(placeholder, value)

    return prompt_text
