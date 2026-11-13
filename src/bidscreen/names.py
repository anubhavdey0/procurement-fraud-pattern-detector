"""Supplier-name normalisation.

Public tender portals identify bidders by a free-text name, so the same firm
shows up as "M/s Northwind Example Enterprise", "NORTHWIND EXAMPLE ENTERPRISE." and
"Northwind Example  Enterprise". This module folds those spellings together.

It is deliberately conservative. Merging two different firms would attach one
firm's bidding history to another, which is worse than missing a match. So it
does not strip plurals, does not fuzzy-match, and does not drop words that
could tell two firms apart.

Name matching cannot separate two people who share a name, and it cannot join
a firm to its own renamed or re-registered self. Both limits are documented in
docs/methodology.md and repeated in every report.
"""

from __future__ import annotations

import re
import unicodedata

# Leading courtesy titles and the "M/s" (Messrs) prefix common in Indian tenders.
_PREFIX_TOKENS = {"ms", "messrs", "mr", "mrs", "shri", "sri", "smt", "dr"}

# Legal-form words mapped to one spelling. Order matters for multi-word forms.
_LEGAL_FORMS = [
    (r"\bprivate\b", "pvt"),
    (r"\blimited\b", "ltd"),
    (r"\bcompany\b", "co"),
    (r"\bcorporation\b", "corp"),
    (r"\bincorporated\b", "inc"),
]

_MS_PREFIX = re.compile(r"^\s*m\s*/\s*s\b\.?", re.IGNORECASE)
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalise_firm_name(name: object) -> str:
    """Return a matching key for a supplier name, or "" when there is none.

    >>> normalise_firm_name("M/s. Northwind Example Enterprise")
    'northwind example enterprise'
    >>> normalise_firm_name("NORTHWIND EXAMPLE  ENTERPRISE.")
    'northwind example enterprise'
    >>> normalise_firm_name("Quillfeather Infra Private Limited")
    'quillfeather infra pvt ltd'
    """
    if name is None:
        return ""
    text = str(name)
    if not text.strip() or text.strip().lower() in {"nan", "none", "null", "na", "n/a"}:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = _MS_PREFIX.sub(" ", text).lower().replace("&", " and ")
    text = _NON_ALNUM.sub(" ", text)
    for pattern, replacement in _LEGAL_FORMS:
        text = re.sub(pattern, replacement, text)
    tokens = text.split()
    while tokens and tokens[0] in _PREFIX_TOKENS:
        tokens.pop(0)
    return " ".join(tokens)
