"""Award price relative to the buyer's estimate.

When only the award value is published, the usable price signal is the ratio

    relative price = award value / pre-tender estimate.

Wachs and Kertesz (2019) use it to check their network screen: groups that
look like cartels on the graph also win at higher relative prices. The same
check is run here. A group whose awards sit near the estimate, while
comparable tenders from the same buyers are won well below it, is paying
little for the appearance of competition.

Two things make this ratio hard to read, and both are common in Indian works
tenders:

* Estimates are set from a schedule of rates and can be out of date. A ratio
  above 1 may reflect a stale estimate.
* Many buyers treat bids more than a fixed percentage below the estimate as
  abnormally low. Bids then pile up exactly at that floor and the winner is
  picked among tied bids. In the Assam data a large share of awards sit at
  exactly 0.90 of the estimate. That pile is a rule at work, not a pattern
  of collusion.

So the screen compares a group with other tenders from the same segments, and
never reads the level of the ratio on its own.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

VALID_RANGE = (0.2, 2.0)
NEAR_ESTIMATE = 0.99
MIN_AWARDS = 5


def relative_price(tenders: pd.DataFrame) -> pd.Series:
    """Award value over estimate, indexed by tender. Ratios outside
    ``VALID_RANGE`` are treated as data errors and dropped."""
    ratio = (tenders["award_value"] / tenders["estimate"]).astype(float)
    ratio.index = tenders["tender_id"].to_numpy()
    ratio = ratio.replace([np.inf, -np.inf], np.nan).dropna()
    return ratio.loc[ratio.between(*VALID_RANGE)].rename("relative_price")


def contested_tenders(bids: pd.DataFrame) -> set:
    """Tenders with at least two identified bidders."""
    bidders = bids.loc[bids["firm"] != ""].groupby("tender_id")["firm"].size()
    return set(bidders.index[bidders >= 2])


def priced_tenders(bids: pd.DataFrame, tenders: pd.DataFrame) -> pd.DataFrame:
    """Every tender with a usable relative price, with its segment and whether
    it was contested. Indexed by tender."""
    ratio = relative_price(tenders)
    out = ratio.to_frame()
    out["segment"] = tenders.set_index("tender_id")["segment"].reindex(out.index).to_numpy()
    out["contested"] = out.index.isin(contested_tenders(bids))
    return out


def group_relative_price(
    bids: pd.DataFrame,
    tenders: pd.DataFrame,
    members: frozenset,
    priced: pd.DataFrame | None = None,
    min_awards: int = MIN_AWARDS,
) -> dict:
    """Relative price of the tenders a group won among itself, against other
    contested tenders from the same segments.

    ``price_p_value`` is a one-sided Mann-Whitney test that the group's
    relative prices are higher than the benchmark's. ``priced`` takes the
    output of ``priced_tenders`` when it has already been computed.
    """
    if priced is None:
        priced = priced_tenders(bids, tenders)

    member_bids = bids.loc[bids["firm"].isin(members)]
    per_tender = member_bids.groupby("tender_id")["firm"].size()
    joint = per_tender.index[per_tender >= 2]
    won_by_member = member_bids.loc[member_bids["won"], "tender_id"]
    group = priced.loc[priced.index.isin(joint) & priced.index.isin(won_by_member)]

    out = {
        "n_priced_awards": int(len(group)),
        "median_relative_price": np.nan,
        "benchmark_median": np.nan,
        "share_near_estimate": np.nan,
        "benchmark_share_near_estimate": np.nan,
        "price_p_value": np.nan,
    }
    if len(group) < min_awards:
        return out

    ratio = group["relative_price"]
    out.update(
        median_relative_price=float(ratio.median()),
        share_near_estimate=float((ratio >= NEAR_ESTIMATE).mean()),
    )
    benchmark = priced.loc[
        priced["contested"]
        & priced["segment"].isin(set(group["segment"].dropna()))
        & ~priced.index.isin(joint),
        "relative_price",
    ]
    if len(benchmark) < min_awards:
        return out
    test = stats.mannwhitneyu(ratio, benchmark, alternative="greater")
    out.update(
        benchmark_median=float(benchmark.median()),
        benchmark_share_near_estimate=float((benchmark >= NEAR_ESTIMATE).mean()),
        price_p_value=float(test.pvalue),
    )
    return out
