"""Leave-one-case-out validation: learn on the other cases, score the one set aside."""

import dataclasses

import numpy as np
import pandas as pd
import pytest

from bidscreen import validate
from bidscreen.report import build_report
from bidscreen.screens.price import PRICE_SCREENS
from bidscreen.synthetic import make_market

CASES = [(0, "brazil"), (1, "italy"), (2, "usa")]


def labelled_set(flip: str | None = None):
    """Three synthetic markets named after real cases. ``flip`` inverts the
    cartel labels of one of them."""
    markets = []
    for seed, name in CASES:
        market = dataclasses.replace(make_market(seed=seed), name=name)
        if name == flip:
            tenders = market.tenders.assign(collusive=~market.tenders["collusive"].astype(bool))
            market = dataclasses.replace(market, tenders=tenders)
        markets.append(market)
    return markets


@pytest.fixture(scope="module")
def held_out():
    return validate.leave_one_case_out(labelled_set(), n_boot=20)


def test_every_case_is_scored_by_every_method(held_out):
    scores, rules = held_out
    assert len(scores) == len(CASES) * len(validate.LOCO_METHODS)
    assert set(scores["method"]) == set(validate.LOCO_METHODS)
    assert list(rules["market"]) == [name for _, name in CASES]
    # A planted cartel that bids as the literature expects is found on every
    # case whichever way the score is learned.
    assert (scores["auc"] > 0.8).all()
    chosen = scores.loc[scores["method"] == "best_elsewhere", "detail"]
    assert set(chosen) <= set(PRICE_SCREENS)


def test_the_case_set_aside_does_not_shape_what_is_learned(held_out):
    """Invert the labels of one case. If nothing was learned from it, every
    score on it turns into its mirror image and the tuned rule stays put."""
    scores, rules = held_out
    flipped_scores, flipped_rules = validate.leave_one_case_out(labelled_set(flip="usa"), n_boot=0)
    before = scores.loc[scores["market"] == "usa"].set_index("method")
    after = flipped_scores.loc[flipped_scores["market"] == "usa"].set_index("method")
    for method in ("best_elsewhere", "learned_weights"):
        assert after.loc[method, "auc"] == pytest.approx(1 - before.loc[method, "auc"])
        assert after.loc[method, "detail"] == before.loc[method, "detail"]
    rule_before = rules.set_index("market").loc["usa", ["cv_below", "rd_above"]]
    rule_after = flipped_rules.set_index("market").loc["usa", ["cv_below", "rd_above"]]
    assert list(rule_after) == list(rule_before)


def test_fitted_weights_find_the_screen_that_carries_the_signal():
    rng = np.random.default_rng(0)
    features, labels = [], []
    for n, base_rate in ((400, 0.2), (900, 0.7)):
        frame = pd.DataFrame(rng.uniform(size=(n, len(PRICE_SCREENS))), columns=list(PRICE_SCREENS))
        # Only the variance screen says anything, and the share of cartel
        # tenders differs between the two markets.
        logit = 6 * (frame["cv"] - 0.5) + np.log(base_rate / (1 - base_rate))
        labels.append(rng.uniform(size=n) < 1 / (1 + np.exp(-logit)))
        features.append(frame)
    weights = dict(zip(PRICE_SCREENS, validate.fit_weights(features, labels), strict=True))
    assert weights["cv"] > 3
    assert all(abs(w) < 1 for key, w in weights.items() if key != "cv")


def test_tuned_rule_recovers_the_thresholds_that_made_the_labels():
    rng = np.random.default_rng(1)
    screens, labels = [], []
    for n in (600, 1500):
        frame = pd.DataFrame({"cv": rng.uniform(0, 0.2, n), "rd": rng.uniform(0, 3, n)})
        screens.append(frame)
        labels.append(((frame["cv"] < 0.05) & (frame["rd"] > 1.0)).to_numpy())
    assert validate.learn_rule(screens, labels) == (0.05, 1.0)


def test_report_shows_the_held_out_check(held_out, result, tmp_path):
    scores, rules = held_out
    markets = labelled_set()
    validation = {
        "price": pd.concat(
            [validate.price_screen_validation(m, n_boot=0) for m in markets], ignore_index=True
        ),
        "rule": pd.DataFrame([validate.benchmark_rule(m) for m in markets]),
        "loco": scores,
        "loco_rule": rules,
    }
    html = build_report(result, tmp_path, key=b"k", validation=validation).read_text("utf-8")
    assert "Learned on five cases, tested on the sixth" in html
    assert "Rule tuned on the other five" in html
    assert html.count('<tr><th scope="row">Brazil: Petrobras</th><td>') == 1
