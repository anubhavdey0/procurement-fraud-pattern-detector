"""Check the screens against documented cartel cases.

Each labelled market says which tenders and which firms an authority or court
tied to a cartel. That lets every screen be scored on a simple question: if a
reviewer worked down the list this screen produces, would they reach the
cartel's tenders faster than by picking at random?

The score is the AUC: the probability that a randomly chosen cartel tender
ranks above a randomly chosen competitive one. 0.5 is a coin toss. Below 0.5
means the screen points the wrong way in that market.

These are in-sample descriptive checks on six cases. They show where a screen
has carried signal. They are not a promise about the next market.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from bidscreen import graph
from bidscreen.leads import ScreenResult, lead_tenders
from bidscreen.model import Market
from bidscreen.screens.price import PRICE_SCREENS, oriented, tender_price_screens

COMPOSITE = "composite"
# Benchmark rule used by Imhof, Karagok and Rutz (2018) on Swiss road tenders:
# bids unusually close together, with the winner set clearly apart.
BENCHMARK_CV = 0.06
BENCHMARK_RD = 1.0


def auc(score: np.ndarray, label: np.ndarray) -> float:
    """Area under the ROC curve, from ranks. NaN scores are dropped."""
    score = np.asarray(score, dtype=float)
    label = np.asarray(label, dtype=bool)
    keep = np.isfinite(score)
    score, label = score[keep], label[keep]
    n_pos, n_neg = int(label.sum()), int((~label).sum())
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    ranks = stats.rankdata(score)
    return float((ranks[label].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def bootstrap_auc(
    score: np.ndarray, label: np.ndarray, n_boot: int = 500, seed: int = 0
) -> tuple[float, float, float]:
    """AUC with a 95% percentile bootstrap interval over tenders."""
    score = np.asarray(score, dtype=float)
    label = np.asarray(label, dtype=bool)
    keep = np.isfinite(score)
    score, label = score[keep], label[keep]
    point = auc(score, label)
    if not np.isfinite(point):
        return point, float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(n_boot):
        idx = rng.integers(0, score.size, score.size)
        value = auc(score[idx], label[idx])
        if np.isfinite(value):
            draws.append(value)
    if not draws:
        return point, float("nan"), float("nan")
    low, high = np.percentile(draws, [2.5, 97.5])
    return point, float(low), float(high)


def composite_score(screens: pd.DataFrame) -> pd.Series:
    """A training-free summary of the price screens.

    Each screen is turned into a rank within the market, flipped so that a
    high rank is what the literature expects under collusion, and the ranks
    are averaged. Nothing is fitted to the labels.
    """
    ranked = oriented(screens).rank(pct=True)
    return ranked.mean(axis=1, skipna=True).rename(COMPOSITE)


def price_screen_validation(
    market: Market, min_bids: int = 3, n_boot: int = 500, seed: int = 0
) -> pd.DataFrame:
    """AUC of each price screen for telling cartel tenders from the rest."""
    screens = tender_price_screens(market.bids)
    screens = screens.loc[screens["n_bids"] >= min_bids]
    label = market.tenders.set_index("tender_id")["collusive"].reindex(screens.index)
    known = label.notna()
    screens, label = screens.loc[known], label.loc[known].astype(bool).to_numpy()
    scores = oriented(screens)
    scores[COMPOSITE] = composite_score(screens)

    rows = []
    for key in [*PRICE_SCREENS, COMPOSITE]:
        point, low, high = bootstrap_auc(scores[key].to_numpy(), label, n_boot, seed)
        usable = np.isfinite(scores[key].to_numpy())
        rows.append(
            {
                "market": market.name,
                "screen": key,
                "expected": PRICE_SCREENS[key].expected if key in PRICE_SCREENS else "high",
                "n_tenders": int(usable.sum()),
                "n_collusive": int(label[usable].sum()),
                "auc": point,
                "auc_low": low,
                "auc_high": high,
            }
        )
    return pd.DataFrame(rows)


def benchmark_rule(market: Market, min_bids: int = 3) -> dict:
    """How the fixed rule "CV below 0.06 and RD above 1" does in a market."""
    screens = tender_price_screens(market.bids)
    screens = screens.loc[screens["n_bids"] >= min_bids].dropna(subset=["cv", "rd"])
    label = market.tenders.set_index("tender_id")["collusive"].reindex(screens.index)
    screens, label = screens.loc[label.notna()], label.dropna().astype(bool)
    flagged = (screens["cv"] < BENCHMARK_CV) & (screens["rd"] > BENCHMARK_RD)
    return _confusion(market.name, flagged.to_numpy(), label.to_numpy())


def cobid_validation(market: Market, min_bids: int = 5) -> pd.DataFrame:
    """Does co-bidding closeness single out pairs of cartel members?

    A pair counts as positive when both firms were named as cartel members.
    Only pairs of firms with at least ``min_bids`` bids each are scored.
    """
    if not (market.has_firms and market.has_firm_labels):
        return pd.DataFrame()
    member = market.bids.groupby("firm")["cartel_member"].max().astype(bool)
    pairs = graph.cobid_pairs(market.bids, market.tenders, min_joint=1)
    pairs = pairs.loc[(pairs["n_a"] >= min_bids) & (pairs["n_b"] >= min_bids)]
    both = (pairs["firm_a"].map(member) & pairs["firm_b"].map(member)).to_numpy()
    scores = {
        "jaccard": pairs["jaccard"].to_numpy(),
        "excess co-bidding": -np.log10(pairs["p_value"].clip(lower=1e-300)).to_numpy(),
        "joint tenders": pairs["n_joint"].to_numpy(dtype=float),
    }
    return pd.DataFrame(
        [
            {
                "market": market.name,
                "score": name,
                "n_pairs": int(len(pairs)),
                "n_cartel_pairs": int(both.sum()),
                "auc": auc(values, both),
            }
            for name, values in scores.items()
        ]
    )


def lead_validation(result: ScreenResult) -> dict:
    """Score the leads the full pipeline produces, tender by tender.

    A tender is flagged when at least two members of a lead group bid on it.
    """
    market = result.market
    label = market.tenders.set_index("tender_id")["collusive"].dropna().astype(bool)
    flagged = label.index.isin(lead_tenders(result)["tender_id"])
    out = _confusion(market.name, flagged, label.to_numpy())
    out["groups"] = int(len(result.groups))
    out["leads"] = int(len(result.leads))
    if market.has_firm_labels and len(result.leads):
        member = market.bids.groupby("firm")["cartel_member"].max().astype(bool)
        in_lead = set().union(*result.leads["members"])
        out["lead_firms"] = len(in_lead)
        out["lead_firm_precision"] = float(np.mean([bool(member.get(f, False)) for f in in_lead]))
        out["firm_base_rate"] = float(member.mean())
    return out


def _confusion(name: str, flagged: np.ndarray, label: np.ndarray) -> dict:
    flagged = np.asarray(flagged, dtype=bool)
    label = np.asarray(label, dtype=bool)
    hits = int((flagged & label).sum())
    base = float(label.mean()) if label.size else float("nan")
    precision = hits / flagged.sum() if flagged.sum() else float("nan")
    return {
        "market": name,
        "n_tenders": int(label.size),
        "n_collusive": int(label.sum()),
        "base_rate": base,
        "n_flagged": int(flagged.sum()),
        "precision": float(precision),
        "recall": float(hits / label.sum()) if label.sum() else float("nan"),
        "lift": float(precision / base) if base and np.isfinite(precision) else float("nan"),
    }
