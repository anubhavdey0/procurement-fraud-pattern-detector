"""Pseudonyms for firms, tenders and buyers.

Nothing leaves this package under a real name. Reports, tables and figures
carry labels such as ``FIRM-0042``. The labels are:

* keyed: derived with HMAC-SHA256 from a secret that stays on the analyst's
  machine, so nobody can recover a name by hashing a list of candidate names;
* stable: the same secret and the same data give the same labels, so a lead
  can be followed across runs;
* opaque: the label is a rank in digest order, not the digest, so it carries
  no information about the name.

The secret lives in ``data/private/pseudonym.key`` and is ignored by git.
Whoever holds it can rebuild the mapping, which is how a reviewer with a
legitimate reason gets from a lead back to the public tender records.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

KEY_ENV_VAR = "BIDSCREEN_KEY"
DEFAULT_KEY_PATH = Path("data/private/pseudonym.key")

_PREFIX = {"firm": "FIRM", "tender": "TENDER", "buyer": "BUYER"}
_WORD = re.compile(r"[a-z0-9]+")


def load_or_create_key(path: Path | str = DEFAULT_KEY_PATH) -> bytes:
    """Return the pseudonym key, creating one on first use.

    The environment variable ``BIDSCREEN_KEY`` wins over the file so that a
    shared key can be supplied without writing it to disk.
    """
    from_env = os.environ.get(KEY_ENV_VAR)
    if from_env:
        return from_env.encode("utf-8")
    path = Path(path)
    if path.exists():
        key = path.read_text(encoding="utf-8").strip()
        if key:
            return key.encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_hex(32)
    path.write_text(key + "\n", encoding="utf-8")
    return key.encode("utf-8")


class Pseudonymizer:
    """Maps real identifiers to labels like ``FIRM-0042``."""

    def __init__(self, key: bytes) -> None:
        if not key:
            raise ValueError("a non-empty key is required")
        self._key = key
        self._maps: dict[str, dict[str, str]] = {}

    def fit(self, kind: str, values: Iterable[object]) -> Pseudonymizer:
        """Assign labels to every distinct value of one kind."""
        if kind not in _PREFIX:
            raise ValueError(f"unknown kind {kind!r}; expected one of {sorted(_PREFIX)}")
        distinct = sorted({str(v) for v in values if v is not None and str(v) != ""})
        ranked = sorted(distinct, key=lambda v: self._digest(kind, v))
        width = max(4, len(str(len(ranked))))
        self._maps[kind] = {
            value: f"{_PREFIX[kind]}-{rank:0{width}d}" for rank, value in enumerate(ranked, start=1)
        }
        return self

    def label(self, kind: str, value: object) -> str:
        """Return the label for one value. Raises if the value was never fitted."""
        mapping = self._maps.get(kind)
        if mapping is None:
            raise KeyError(f"no labels fitted for {kind!r}")
        try:
            return mapping[str(value)]
        except KeyError:
            raise KeyError(f"{kind} value was not seen when labels were fitted") from None

    def labels(self, kind: str, values: Iterable[object]) -> list[str]:
        return [self.label(kind, v) for v in values]

    def series(self, kind: str, values: pd.Series) -> pd.Series:
        """Label a whole column, keeping missing values missing."""
        mapping = self._maps.get(kind)
        if mapping is None:
            raise KeyError(f"no labels fitted for {kind!r}")
        return values.astype("string").map(mapping)

    def mapping(self, kind: str) -> pd.DataFrame:
        """The private key table for one kind. Never write this anywhere public."""
        mapping = self._maps.get(kind, {})
        return pd.DataFrame({"label": list(mapping.values()), "value": list(mapping.keys())})

    def _digest(self, kind: str, value: str) -> bytes:
        message = f"{kind}\x1f{value}".encode()
        return hmac.new(self._key, message, hashlib.sha256).digest()


def _tokens(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def assert_no_leak(
    text: str,
    real_values: Iterable[object],
    *,
    allow: str = "",
    min_length: int = 6,
) -> None:
    """Raise if any real identifier appears in ``text``.

    Used as a last check before a report is written. Matching is on whole
    words, so a bidder registered under the name "contractor" does not trip
    on the word "contractors" in the page's own wording.

    ``allow`` is the page's fixed wording (template and captions). An
    identifier that occurs there is an ordinary phrase and not a name, so it
    is skipped. Identifiers shorter than ``min_length`` characters are skipped
    too, because they collide with ordinary words.
    """
    page_tokens = _tokens(text)
    words = set(page_tokens)
    haystack = " " + " ".join(page_tokens) + " "
    allowed = " " + " ".join(_tokens(allow)) + " "
    leaked = 0
    for value in real_values:
        needle_tokens = _tokens(str(value))
        needle = " ".join(needle_tokens)
        if len(needle) < min_length or not all(token in words for token in needle_tokens):
            continue
        padded = f" {needle} "
        if padded in haystack and padded not in allowed:
            leaked += 1
    if leaked:
        raise AssertionError(
            f"{leaked} real identifier(s) appear in output that should be pseudonymised; "
            "nothing was written"
        )
