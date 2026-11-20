import itertools

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from bidscreen.screens import cover, pricing, rotation

# ---------------------------------------------------------------- rotation


def test_count_runs():
    assert rotation.count_runs([]) == 0
    assert rotation.count_runs(list("AAAA")) == 1
    assert rotation.count_runs(list("ABAB")) == 4
    assert rotation.count_runs(list("AABBBA")) == 3


def test_expected_runs_matches_enumeration():
    sequence = "AAABBCC"
    runs = [rotation.count_runs(p) for p in itertools.permutations(sequence)]
    mean, variance = rotation.expected_runs([3, 2, 2])
    assert mean == pytest.approx(np.mean(runs))
    assert variance == pytest.approx(np.var(runs))


def test_strict_alternation_is_flagged():
    out = rotation.rotation_test(["A", "B"] * 5)
    assert out["runs"] == 10 and out["n_winners"] == 2
    assert out["z"] > 0
    assert out["p_value"] < 0.05


def test_streaks_are_not_rotation():
    out = rotation.rotation_test(["A"] * 6 + ["B"] * 6)
    assert out["z"] < 0
    assert out["p_value"] > 0.95


def test_a_dominant_winner_does_not_trigger():
    # One firm wins most tenders; the order is as mixed as chance allows.
    rng = np.random.default_rng(0)
    winners = rng.permutation(["A"] * 20 + ["B"] * 4)
    assert rotation.rotation_test(winners)["p_value"] > 0.05


def test_too_little_data_returns_nan():
    assert np.isnan(rotation.rotation_test(["A", "A", "A"])["p_value"])
    assert np.isnan(rotation.rotation_test([])["p_value"])


def test_simultaneous_tenders_are_not_given_an_order():
    winners = ["A", "B"] * 6
    in_order = rotation.rotation_test(winners, order=list(range(12)))
    all_tied = rotation.rotation_test(winners, order=[0] * 12)
    assert in_order["runs"] == 12
    assert all_tied["runs"] < in_order["runs"]
    assert all_tied["p_value"] > in_order["p_value"]


def test_group_rotation_on_the_planted_cartel(market):
    cartel = frozenset(f for f in market.bids["firm"].unique() if f.startswith("Cartel"))
    out = rotation.group_rotation(market.bids, market.tenders, cartel)
    assert out["n_joint_tenders"] == 48
    assert out["inside_win_share"] == pytest.approx(1.0)
    assert out["n_winners"] == 3
    assert out["p_value"] < 0.01


# ------------------------------------------------------------------- cover


def test_poisson_binomial_matches_binomial():
    p = np.full(12, 0.3)
    for k in range(13):
        assert cover.poisson_binomial_cdf(k, p) == pytest.approx(stats.binom.cdf(k, 12, 0.3))


def test_poisson_binomial_matches_enumeration():
    p = np.array([0.5, 0.25, 0.2, 1 / 3])
    for k in range(5):
        total = 0.0
        for outcome in itertools.product([0, 1], repeat=4):
            if sum(outcome) <= k:
                total += np.prod([q if hit else 1 - q for q, hit in zip(p, outcome, strict=True)])
        assert cover.poisson_binomial_cdf(k, p) == pytest.approx(total)
    assert cover.poisson_binomial_cdf(-1, p) == 0.0
    assert cover.poisson_binomial_cdf(9, p) == 1.0


def test_win_expectations(tiny_bids):
    scored = cover.win_expectations(tiny_bids)
    assert "T5" not in set(scored["tender_id"])  # one bidder: nothing to expect
    t1 = scored.loc[scored["tender_id"] == "T1", "p_win"]
    assert t1.to_numpy() == pytest.approx([1 / 3] * 3)


def test_persistent_loser_is_found(market):
    table = cover.persistent_losers(market.bids, min_bids=10)
    worst = table.iloc[0]
    assert worst["firm"] == "Cartel firm 4"
    assert worst["wins"] == 0
    assert worst["p_low"] < 1e-4
    assert worst["expected_wins"] > 8


def test_group_cover_needs_a_large_shortfall():
    # B wins a third of what equal odds would give: weak, but not "never wins".
    rows = []
    for i in range(30):
        rows += [(f"t{i}", "A", i >= 5), (f"t{i}", "B", i < 5)]
    bids = pd.DataFrame(rows, columns=["tender_id", "firm", "won"])
    out = cover.group_cover(bids, frozenset("AB"), min_bids=10)
    assert out["n_members_tested"] == 2
    assert out["n_persistent_losers"] == 0
    strict = cover.group_cover(bids, frozenset("AB"), min_bids=10, max_win_ratio=0.5)
    assert strict["persistent_losers"] == ["B"]


# ----------------------------------------------------------------- pricing


def test_relative_price_drops_impossible_ratios():
    tenders = pd.DataFrame(
        {
            "tender_id": ["a", "b", "c", "d", "e"],
            "estimate": [100.0, 100.0, 100.0, 0.0, np.nan],
            "award_value": [95.0, 4000.0, 1.0, 50.0, 50.0],
        }
    )
    ratio = pricing.relative_price(tenders)
    assert list(ratio.index) == ["a"]
    assert ratio["a"] == pytest.approx(0.95)


def test_group_price_against_same_segment_only(market):
    cartel = frozenset(f for f in market.bids["firm"].unique() if f.startswith("Cartel"))
    out = pricing.group_relative_price(market.bids, market.tenders, cartel)
    assert out["n_priced_awards"] == 48
    assert out["median_relative_price"] > 0.98
    assert out["benchmark_median"] < 0.90
    assert out["share_near_estimate"] > out["benchmark_share_near_estimate"]
    assert out["price_p_value"] < 1e-6


def test_group_price_needs_enough_awards(market):
    out = pricing.group_relative_price(market.bids, market.tenders, frozenset({"nobody"}))
    assert out["n_priced_awards"] == 0
    assert np.isnan(out["price_p_value"])


def test_group_rotation_does_not_depend_on_row_order(market):
    # Same-day tenders force the tie-breaking path.
    tenders = market.tenders.assign(order=market.tenders["order"] // 86400 // 30)
    cartel = frozenset(f for f in market.bids["firm"].unique() if f.startswith("Cartel"))
    first = rotation.group_rotation(market.bids, tenders, cartel)
    shuffled = market.bids.sample(frac=1.0, random_state=3)
    second = rotation.group_rotation(shuffled, tenders, frozenset(sorted(cartel, reverse=True)))
    assert first == second
