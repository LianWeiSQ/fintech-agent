BASE_SYSTEM_PROMPT = (
    "You are the report agent. Turn audited market intelligence into a concise "
    "Chinese research brief with clear evidence boundaries."
)


def build_system_prompt(skill_body: str) -> str:
    parts = [BASE_SYSTEM_PROMPT]
    if skill_body:
        parts.append("Agent skill instructions:\n" + skill_body)
    return "\n\n".join(parts)
