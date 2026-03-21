BASE_SYSTEM_PROMPT = (
    "You are the event intelligence agent. Normalize news into canonical events, "
    "keep chronology, preserve evidence, and avoid fabricating detail."
)
TRANSLATION_INSTRUCTION = (
    "Translate market news into concise Chinese for professional traders. "
    "Keep names, dates, and numbers intact."
)


def build_system_prompt(skill_body: str) -> str:
    parts = [BASE_SYSTEM_PROMPT]
    if skill_body:
        parts.append("Agent skill instructions:\n" + skill_body)
    return "\n\n".join(parts)
