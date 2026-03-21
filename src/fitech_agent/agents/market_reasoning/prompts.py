BASE_SYSTEM_PROMPT = (
    "You are the market reasoning agent. Map events into asset impact, respect evidence "
    "quality, and prefer explicit transmission paths over vague narratives."
)


def build_system_prompt(skill_body: str) -> str:
    parts = [BASE_SYSTEM_PROMPT]
    if skill_body:
        parts.append("Agent skill instructions:\n" + skill_body)
    return "\n\n".join(parts)
