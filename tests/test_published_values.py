"""Compare the price screens with the values published alongside the cartel
case files. Skipped when the files have not been downloaded."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from bidscreen.ingest import LABELLED_CASES
from bidscreen.screens.price import bid_screens

RAW = Path(__file__).resolve().parents[1] / "data" / "raw" / "labelled"
PUBLISHED = {"cv": "CV", "spd": "SPD", "skew": "SKEW", "kurt": "KURT", "ks": "KSTEST"}


@pytest.mark.parametrize("key", list(LABELLED_CASES))
def test_screens_reproduce_published_columns(key):
    path = RAW / LABELLED_CASES[key].filename
    if not path.exists():
        pytest.skip("cartel case files not downloaded; run `bidscreen fetch labelled`")
    frame = pd.read_excel(path)
    checked = 0
    for _, tender in frame.groupby("Tender"):
        if len(tender) < 4:
            continue
        ours = bid_screens(tender["Bid_value"].to_numpy(dtype=float))
        for name, column in PUBLISHED.items():
            if np.isfinite(ours[name]):
                # The files carry four decimals.
                assert ours[name] == pytest.approx(tender[column].iloc[0], abs=1.5e-4)
                checked += 1
    assert checked > 100
