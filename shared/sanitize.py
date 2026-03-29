"""Input sanitization utilities for LLM prompt injection defense."""


def delimit_user_input(value: str, label: str = "user_input") -> str:
    """Wrap user-provided text in XML-style delimiters to reduce prompt injection.

    Strips any pre-existing delimiter tags the user might inject to escape the boundary.
    """
    sanitized = value.replace(f"</{label}>", "").replace(f"<{label}>", "")
    return f"<{label}>{sanitized}</{label}>"
