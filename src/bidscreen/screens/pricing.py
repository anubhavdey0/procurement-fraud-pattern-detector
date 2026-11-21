"""Award price relative to the buyer's estimate.

When only the award value is published, the usable price signal is the ratio

    relative price = award value / pre-tender estimate.

Wachs and Kertesz (2019) use it to check their network screen: groups that
look like cartels on the graph also win at higher relative prices. The same
check is run here. A group whose awards sit near the estimate, while
comparable tenders from the same buyers are won well below it, is paying
little for the appearance of competition.

Three things make this ratio hard to read, and all are common in Indian works
tenders:

* Estimates are set from a schedule of rates and can be out of date. A ratio
  above 1 may reflect a stale estimate.
* Many buyers treat bids more than a fixed percentage below the estimate as
  abnormally low. Bids then pile up exactly at that floor and the winner is
  picked among tied bids. In the Assam data a large share of awards sit at
  exactly 0.90 of the estimate. That pile is a rule at work, not a pattern
  of collusion.
* Fewer bidders means less pressure on price. A group found by the co-bidding
  screen tends to bid where few others do, so its awards would sit nearer the
  estimate even if every bid were honest. Compared with all tenders, the
  screen would mostly repeat what the closed-group screen already says.

So a group's awards are only compared with tenders from the same segment that
drew the same number of bidders (``BIDDER_BANDS``), and the level of the ratio
is never read on its own. The comparisons are combined across segments and
bidder counts with the stratified Wilcoxon test of van Elteren (1960).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

VALID_RANGE = (0.2, 2.0)
NEAR_ESTIMATE = 0.99
MIN_AWARDS = 5
# Lower edges of the bidder-count bands: 2, 3, 4, 5 to 6, 7 or more.
BIDDER_BANDS = (2, 3, 4, 5, 7)


def relative_price(tenders: pd.DataFrame) -> pd.Series:
    """Award value over estimate, indexed by tender. Ratios outside
    ``VALID_RANGE`` are treated as data errors and dropped."""
    ratio = (tenders["award_value"] / tenders["estimate"]).astype(float)
    ratio.index = tenders["tender_id"].to_numpy()
    ratio = ratio.replace([np.inf, -np.inf], np.nan).dropna()
    return ratio.loc[ratio.between(*VALID_RANGE)].rename("relative_price")


def bidder_counts(bids: pd.DataFrame) -> pd.Series:
    """Identified bidders per tender."""
    return bids.loc[bids["firm"] != ""].groupby("tender_id")["firm"].size()


def contested_tenders(bids: pd.DataFrame) -> set:
    """Tenders with at least two identified bidders."""
    counts = bidder_counts(bids)
    return set(counts.index[counts >= 2])


def bidder_band(n_bidders) -> np.ndarray:
    """The lower edge of the ``BIDDER_BANDS`` band each count falls in; 0
    below two bidders."""
    n = np.nan_to_num(np.asarray(n_bidders, dtype=float), nan=0.0)
    edges = np.asarray(BIDDER_BANDS)
    index = np.searchsorted(edges, n, side="right") - 1
    return np.where(index >= 0, edges[np.clip(index, 0, None)], 0)


def priced_tenders(bids: pd.DataFrame, tenders: pd.DataFrame) -> pd.DataFrame:
    """Every tender with a usable relative price, with its segment, its number
    of identified bidders and the band that number falls in. Indexed by
    tender."""
    ratio = relative_price(tenders)
    out = ratio.to_frame()
    out["segment"] = tenders.set_index("tender_id")["segment"].reindex(out.index).to_numpy()
    n = bidder_counts(bids).reindex(out.index).fillna(0).astype(int)
    out["n_bidders"] = n.to_numpy()
    out["band"] = bidder_band(out["n_bidders"])
    out["contested"] = out["n_bidders"] >= 2
    return out


def stratified_rank_test(x, x_strata, y, y_strata) -> dict:
    """One-sided test that ``x`` tends to be larger than ``y`` within strata.

    Van Elteren's test: a Wilcoxon rank-sum statistic is computed in every
    stratum that holds both samples, and the statistics are summed with
    weights 1 / (stratum size + 1). The p-value uses the normal approximation
    with the variance corrected for ties. With a single stratum it is the
    Mann-Whitney test.

    Returns ``z``, ``p_value``, and how many of each sample sat in strata
    that held the other (``n_x``, ``n_y``). Strata holding only one sample
    carry no information and are skipped.
    """
    x = pd.Series(np.asarray(x, dtype=float), index=np.asarray(x_strata, dtype=object))
    y = pd.Series(np.asarray(y, dtype=float), index=np.asarray(y_strata, dtype=object))
    shared = sorted(set(x.index) & set(y.index), key=str)
    total, variance, n_x, n_y = 0.0, 0.0, 0, 0
    for stratum in shared:
        a, b = x.loc[[stratum]].to_numpy(), y.loc[[stratum]].to_numpy()
        m, n = a.size, b.size
        size = m + n
        ranks = stats.rankdata(np.concatenate([a, b]))
        _, ties = np.unique(np.concatenate([a, b]), return_counts=True)
        tie_term = float((ties**3 - ties).sum()) / (size * (size - 1))
        weight = 1.0 / (size + 1)
        total += weight * (ranks[:m].sum() - m * (size + 1) / 2)
        variance += weight**2 * m * n / 12 * ((size + 1) - tie_term)
        n_x, n_y = n_x + m, n_y + n
    out = {"z": np.nan, "p_value": np.nan, "n_x": n_x, "n_y": n_y}
    if not shared:
        return out
    if variance <= 0:
        # Every value tied in every stratum: nothing points either way.
        out.update(z=0.0, p_value=1.0)
        return out
    z = total / np.sqrt(variance)
    out.update(z=float(z), p_value=float(stats.norm.sf(z)))
    return out


def weighted_median(values, weights) -> float:
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    order = np.argsort(values, kind="stable")
    cumulative = np.cumsum(weights[order])
    return float(values[order][np.searchsorted(cumulative, cumulative[-1] / 2)])


def group_relative_price(
    bids: pd.DataFrame,
    tenders: pd.DataFrame,
    members: frozenset,
    priced: pd.DataFrame | None = None,
    min_awards: int = MIN_AWARDS,
) -> dict:
    """Relative price of the tenders a group won among itself, against other
    tenders from the same segments that drew as many bidders.

    ``price_p_value`` comes from ``stratified_rank_test`` with segment and
    bidder band as strata. Only the group's awards that have such tenders to
    compare with are used; ``n_priced_awards`` counts them once the test has
    run. The benchmark figures are weighted to the group's mix of strata, so
    they show what the same kind of tender fetched elsewhere. ``priced``
    takes the output of ``priced_tenders`` when it has already been computed.
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
        "n_benchmark": 0,
        "median_relative_price": np.nan,
        "benchmark_median": np.nan,
        "share_near_estimate": np.nan,
        "benchmark_share_near_estimate": np.nan,
        "price_z": np.nan,
        "price_p_value": np.nan,
    }
    if len(group) < min_awards:
        return out
    out.update(
        median_relative_price=float(group["relative_price"].median()),
        share_near_estimate=float((group["relative_price"] >= NEAR_ESTIMATE).mean()),
    )

    benchmark = priced.loc[
        priced["contested"]
        & priced["segment"].isin(set(group["segment"].dropna()))
        & ~priced.index.isin(joint)
    ]
    group_strata = _strata(group)
    bench_strata = _strata(benchmark)
    shared = np.intersect1d(group_strata.unique(), bench_strata.unique())
    matched = group.loc[group_strata.isin(shared).to_numpy()]
    compared = benchmark.loc[bench_strata.isin(shared).to_numpy()]
    if len(matched) < min_awards or len(compared) < min_awards:
        return out

    test = stratified_rank_test(
        matched["relative_price"], _strata(matched), compared["relative_price"], _strata(compared)
    )
    # Each benchmark tender stands for its stratum's share of the group.
    group_share = _strata(matched).value_counts()
    bench_size = _strata(compared).value_counts()
    weight = _strata(compared).map(group_share / bench_size).to_numpy(dtype=float)
    ratio, bench = matched["relative_price"], compared["relative_price"].to_numpy()
    out.update(
        n_priced_awards=int(len(matched)),
        n_benchmark=int(len(compared)),
        median_relative_price=float(ratio.median()),
        share_near_estimate=float((ratio >= NEAR_ESTIMATE).mean()),
        benchmark_median=weighted_median(bench, weight),
        benchmark_share_near_estimate=float(weight[bench >= NEAR_ESTIMATE].sum() / weight.sum()),
        price_z=test["z"],
        price_p_value=test["p_value"],
    )
    return out


def _strata(frame: pd.DataFrame) -> pd.Series:
    return frame["segment"].astype(str) + " | " + frame["band"].astype(str)
