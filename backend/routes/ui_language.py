"""
Validation for the current user's interface language (users.ui_language).

Pure (no Flask, no database) so the unit tests can import it on the CI unit job.
"""

UI_LANGUAGES = ("en", "el")


def parse_ui_language(raw):
    """
    'en' / 'el' (case and surrounding spaces ignored) -> that code.
    None or '' -> None (no saved choice: the client follows the browser).
    Anything else -> ValueError.
    """
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError("ui_language must be 'en', 'el' or null")
    value = raw.strip().lower()
    if value == "":
        return None
    if value not in UI_LANGUAGES:
        raise ValueError("ui_language must be 'en', 'el' or null")
    return value
