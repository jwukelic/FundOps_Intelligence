from __future__ import annotations

import re
import unicodedata

from app.models import SignalRecord

# Legal/organisational suffixes that should be stripped before comparison so
# that "Acme LLC" and "Acme" resolve to the same entity key.
_ORG_SUFFIXES: tuple[str, ...] = (
    "llc", "l.l.c", "inc", "incorporated", "corp", "corporation",
    "ltd", "limited", "lp", "l.p", "llp", "l.l.p",
    "foundation", "fund", "trust", "assoc", "association",
    "co", "company",
    "nonprofit", "non-profit", "npo", "ngo",
    "institute",
)

# Pattern: trailing suffix (with optional comma or period before it)
_SUFFIX_RE = re.compile(
    r"[,.]?\s+(?:" + "|".join(re.escape(s) for s in _ORG_SUFFIXES) + r")\.?$",
    re.IGNORECASE,
)

# Characters that are purely punctuation noise between words
_PUNCT_RE = re.compile(r"""[\"'`\u2018\u2019\u201c\u201d&@#$%^*+=|\\/<>{}\[\]~]""")

# Collapse runs of whitespace and dashes/underscores to a single space
_SPACE_RE = re.compile(r"[\s\-_]+")


def normalise_name(name: str) -> str:
    """Return a canonical form of *name* suitable for entity-key comparison.

    The canonical form is:
    1. Unicode NFKC-normalised (resolves ligatures, full-width chars, etc.)
    2. Punctuation noise stripped.
    3. Legal/organisational suffixes removed (iteratively, so "Acme, Inc." and
       "Acme Inc" both become "acme").
    4. Whitespace collapsed and the whole thing lowercased.
    """
    # Step 1 – unicode normalisation
    name = unicodedata.normalize("NFKC", name)
    # Step 2 – strip punctuation noise (keep hyphens/spaces for step 3)
    name = _PUNCT_RE.sub(" ", name)
    # Step 3 – collapse whitespace, hyphens, underscores so suffix regex can match
    name = _SPACE_RE.sub(" ", name).strip()
    # Step 4 – strip org suffixes iteratively (handles stacked suffixes like
    # "Acme Corp Foundation")
    prev = None
    while prev != name:
        prev = name
        name = _SUFFIX_RE.sub("", name).strip()
    # Step 5 – final lowercase
    return name.lower()


def canonical_entity_key(signal: SignalRecord) -> str:
    """Return the normalised entity key for *signal*.

    For account entities the key is the normalised organisation name.
    For all other entity types the key is a simple lowercase/strip.
    """
    raw = signal.entity_key.strip()
    if signal.entity_type == "account":
        return normalise_name(raw)
    return raw.lower()

