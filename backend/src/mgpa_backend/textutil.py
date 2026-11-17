"""Small text helpers shared by several domain modules (no imports from the app, so no cycles)."""

import re


def normalize(text: str) -> str:
    """Case-, space- and punctuation-insensitive key: "Rev. Butterfly" == "rev butterfly"."""
    return re.sub(r"[^\w]+", " ", text.casefold()).strip()
