"""Text normalization applied before features, the same at training and at serving time."""

import re
import unicodedata

_DIACRITICS = re.compile(r"[ً-ْٰ]")  # harakat, tanwin, shadda, sukun, dagger alef
_TATWEEL = "ـ"
_ALEF = re.compile(r"[آأإ]")  # alef with madda or hamza above or below
_SPACE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """NFKC, Arabic orthographic variants folded, whitespace collapsed. Case is left to the vectorizer."""
    text = unicodedata.normalize("NFKC", text)
    text = _DIACRITICS.sub("", text).replace(_TATWEEL, "")
    text = _ALEF.sub("ا", text).replace("ى", "ي")  # alef maqsura to ya
    return _SPACE.sub(" ", text).strip()
