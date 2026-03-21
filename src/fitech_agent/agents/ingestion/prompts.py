BASE_SYSTEM_PROMPT = (
    "You are the ingestion agent for a market research pipeline. "
    "Collect and preserve raw evidence faithfully."
)


def build_system_prompt(skill_body: str) -> str:
    parts = [BASE_SYSTEM_PROMPT]
    if skill_body:
        parts.append("Agent skill instructions:\n" + skill_body)
    return "\n\n".join(parts)
