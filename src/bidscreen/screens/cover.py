"""Cover bidding: firms that keep bidding and keep losing.

A cover bid is a bid that is not meant to win. It is there to make a tender
look contested. The OECD Guidelines for Fighting Bid Rigging in Public
Procurement (2009) name the footprint among their warning signs: companies
that always bid and never win. The same indicator appears in the toolkit of
Toth, Fazekas, Czibik and Toth (2014).

Without bid amounts, the footprint has to be read from outcomes. For each
firm, compare the number of tenders it won with the number it would be
expected to win if every bidder in a tender were equally likely to be chosen.
A firm that bids in 30 tenders against three rivals each time would expect
about 7.5 wins. Winning none has probability 0.75 ** 30, about 0.0002.

The null is deliberately crude. Firms differ in cost and quality, and every
market has a fringe of bidders that rarely win for ordinary reasons. So this
screen is weak on its own and is only reported inside a group that the
co-bidding screen has already singled out: a member that keeps appearing next
to the same winners and never wins itself.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

MIN_BIDS = 10
P_THRESHOLD = 0.01
# A persistent loser wins at most this share of what equal odds would give.
# Without it, any firm that is merely less competitive than a strong
# incumbent gets flagged once it has bid often enough.
MAX_WIN_RATIO = 0.25
LOSER_COLUMNS = ["firm", "n_bids", "wins", "expected_wins", "p_low"]


def poisson_binomial_cdf(k: int, probabilities: np.ndarray) -> float:
    """P(X <= k) where X counts successes in independent trials with the
    given success probabilities."""
    if k < 0:
        return 0.0
    p = np.asarray(probabilities, dtype=float)
    if k >= p.size:
        return 1.0
    pmf = np.zeros(k + 1)
    pmf[0] = 1.0
    for prob in p:
        pmf[1:] = pmf[1:] * (1.0 - prob) + pmf[:-1] * prob
        pmf[0] *= 1.0 - prob
    return float(min(pmf.sum(), 1.0))


def win_expectations(bids: pd.DataFrame) -> pd.DataFrame:
    """For every bid on a decided multi-bidder tender, the chance of winning
    under equal odds: winners in the tender divided by bidders in the tender."""
    known = bids.loc[bids["firm"] != "", ["tender_id", "firm", "won"]]
    per_tender = known.groupby("tender_id")["won"].agg(n="size", winners="sum")
    decided = per_tender.loc[(per_tender["n"] >= 2) & (per_tender["winners"] >= 1)]
    out = known.loc[known["tender_id"].isin(decided.index)].copy()
    out["p_win"] = out["tender_id"].map(decided["winners"] / decided["n"])
    return out


def persistent_losers(
    bids: pd.DataFrame,
    firms: frozenset | None = None,
    tender_ids=None,
    min_bids: int = MIN_BIDS,
    expectations: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Wins against expected wins, per firm.

    ``p_low`` is the probability of winning this few tenders or fewer under
    equal odds. Restrict to ``firms`` and ``tender_ids`` to ask the question
    inside one group's joint tenders. Only firms with at least ``min_bids``
    bids on decided tenders are returned. ``expectations`` takes the output
    of ``win_expectations`` when it has already been computed.
    """
    scored = win_expectations(bids) if expectations is None else expectations
    if tender_ids is not None:
        scored = scored.loc[scored["tender_id"].isin(tender_ids)]
    if firms is not None:
        scored = scored.loc[scored["firm"].isin(firms)]
    rows = []
    for firm, block in scored.groupby("firm", sort=False):
        if len(block) < min_bids:
            continue
        wins = int(block["won"].sum())
        rows.append(
            {
                "firm": firm,
                "n_bids": int(len(block)),
                "wins": wins,
                "expected_wins": float(block["p_win"].sum()),
                "p_low": poisson_binomial_cdf(wins, block["p_win"].to_numpy()),
            }
        )
    if not rows:
        return pd.DataFrame(columns=LOSER_COLUMNS)
    return pd.DataFrame(rows, columns=LOSER_COLUMNS).sort_values("p_low").reset_index(drop=True)


def group_cover(
    bids: pd.DataFrame,
    members: frozenset,
    min_bids: int = MIN_BIDS,
    p_threshold: float = P_THRESHOLD,
    max_win_ratio: float = MAX_WIN_RATIO,
    expectations: pd.DataFrame | None = None,
) -> dict:
    """Persistent losers among the members of one group, counted over the
    tenders where at least two members bid.

    A member qualifies when it won at most ``max_win_ratio`` of its expected
    wins. ``min_p_low`` is the smallest p-value among qualifying members and
    ``n_members_tested`` the number of members with enough bids to be tested,
    which is what a multiple-testing correction should use.
    """
    member_bids = bids.loc[bids["firm"].isin(members)]
    per_tender = member_bids.groupby("tender_id")["firm"].size()
    joint = per_tender.index[per_tender >= 2]
    table = persistent_losers(
        bids, firms=members, tender_ids=joint, min_bids=min_bids, expectations=expectations
    )
    short = table.loc[table["wins"] <= max_win_ratio * table["expected_wins"]]
    flagged = short.loc[short["p_low"] < p_threshold]
    return {
        "n_members_tested": int(len(table)),
        "n_persistent_losers": int(len(flagged)),
        "persistent_losers": flagged["firm"].tolist(),
        "min_p_low": float(short["p_low"].min()) if len(short) else np.nan,
        "loser_table": short.reset_index(drop=True),
    }
