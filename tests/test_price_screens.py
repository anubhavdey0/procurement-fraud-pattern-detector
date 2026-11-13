import numpy as np
import pandas as pd
import pytest
from scipy import stats

from bidscreen.screens.price import PRICE_SCREENS, bid_screens, oriented, tender_price_screens


def test_screens_match_hand_calculation():
    # Four evenly spaced bids: every statistic can be worked out on paper.
    s = bid_screens(np.array([120.0, 100.0, 130.0, 110.0]))
    assert s["cv"] == pytest.approx(np.sqrt(500 / 3) / 115)
    assert s["spd"] == pytest.approx(0.30)
    assert s["diffp"] == pytest.approx(0.10)
    assert s["rd"] == pytest.approx(1.0)  # gap of 10 over sd(110, 120, 130) = 10
    assert s["skew"] == pytest.approx(0.0, abs=1e-12)
    assert s["kurt"] == pytest.approx(-1.2)
    assert s["ks"] == pytest.approx(0.25)


def test_ks_matches_scipy():
    rng = np.random.default_rng(1)
    for _ in range(200):
        bids = np.sort(rng.lognormal(10, 0.3, rng.integers(2, 25)))
        expected = stats.kstest(bids, "uniform", args=(bids[0], bids[-1] - bids[0])).statistic
        assert bid_screens(bids)["ks"] == pytest.approx(expected)


def test_cover_bids_look_like_cover_bids():
    competitive = bid_screens(np.array([80.0, 88.0, 97.0, 105.0, 118.0]))
    rigged = bid_screens(np.array([99.0, 104.0, 104.5, 105.0, 105.2]))
    assert rigged["cv"] < competitive["cv"]
    assert rigged["rd"] > 1 > competitive["rd"]
    assert rigged["skew"] < competitive["skew"]


def test_screens_need_enough_bids():
    assert all(np.isnan(v) for v in bid_screens(np.array([100.0])).values())
    two = bid_screens(np.array([100.0, 110.0]))
    assert np.isfinite(two["cv"]) and np.isfinite(two["diffp"])
    assert np.isnan(two["rd"]) and np.isnan(two["skew"]) and np.isnan(two["kurt"])
    three = bid_screens(np.array([100.0, 110.0, 125.0]))
    assert np.isfinite(three["rd"]) and np.isnan(three["kurt"])


def test_identical_bids_do_not_divide_by_zero():
    s = bid_screens(np.array([100.0, 100.0, 100.0, 100.0]))
    assert s["cv"] == 0 and s["spd"] == 0
    assert np.isnan(s["rd"]) and np.isnan(s["skew"]) and np.isnan(s["ks"])


def test_missing_and_non_positive_bids_are_ignored():
    assert all(np.isnan(v) for v in bid_screens(np.array([0.0, 10.0, 20.0])).values())
    with_gap = bid_screens(np.array([100.0, np.nan, 110.0, 120.0]))
    assert with_gap["spd"] == pytest.approx(0.2)


def test_tender_table_skips_unpriced_tenders():
    bids = pd.DataFrame(
        {
            "tender_id": ["a", "a", "a", "b", "b", "c"],
            "bid_value": [100.0, 110.0, 120.0, np.nan, np.nan, 50.0],
        }
    )
    table = tender_price_screens(bids)
    assert list(table.index) == ["a"]
    assert table.loc["a", "n_bids"] == 3
    assert set(PRICE_SCREENS) <= set(table.columns)


def test_oriented_flips_the_low_screens():
    table = pd.DataFrame({"cv": [0.02, 0.20], "rd": [3.0, 0.4]}, index=["rigged", "fair"])
    flipped = oriented(table)
    assert flipped.loc["rigged", "cv"] > flipped.loc["fair", "cv"]
    assert flipped.loc["rigged", "rd"] > flipped.loc["fair", "rd"]
