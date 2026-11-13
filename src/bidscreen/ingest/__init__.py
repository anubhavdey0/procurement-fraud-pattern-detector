"""Loaders that turn each public source into a :class:`bidscreen.model.Market`."""

from bidscreen.ingest.assam import load_assam
from bidscreen.ingest.labelled import LABELLED_CASES, load_labelled

__all__ = ["LABELLED_CASES", "load_assam", "load_labelled"]
