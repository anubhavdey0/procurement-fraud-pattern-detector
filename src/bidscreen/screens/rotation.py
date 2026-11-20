"""Bid rotation: do the members of a group take turns winning?

The OECD Guidelines for Fighting Bid Rigging in Public Procurement (2009) list
bid rotation among the standard schemes: the conspirators keep bidding but
take turns being the winner. Turn-taking has a testable footprint. If wins were
handed out without regard to who won last, the sequence of winners would
change hands about as often as a shuffled copy of itself. Under rotation it
changes hands more often.

The test is the Wald-Wolfowitz runs test for more than two categories (Mood
1940). A run is a stretch of consecutive tenders won by the same firm. Many
runs means frequent alternation. The p-value comes from shuffling the observed
winner sequence, which keeps each firm's number of wins fixed, so a firm that
simply wins more often than the others does not trigger the screen.

Limits: the test needs the tenders in time order, and it needs enough wins to
say anything (eight alternating wins between two firms is the least that
reaches p < 0.05). Tenders opened at the same moment have no order, so their
order is randomised and the statistic averaged. That makes the test
conservative for batches of lots awarded together.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

MIN_WINS = 8


def count_runs(sequence: Sequence) -> int:
    """Number of runs: stretches of equal consecutive items."""
    if len(sequence) == 0:
        return 0
    array = np.asarray(sequence)
    return int(1 + np.count_nonzero(array[1:] != array[:-1]))


def expected_runs(counts: Sequence[int]) -> tuple[float, float]:
    """Mean and variance of the number of runs under random ordering."""
    c = np.asarray(counts, dtype=float)
    n = c.sum()
    if n < 2:
        return float(n), 0.0
    s2, s3 = (c**2).sum(), (c**3).sum()
    mean = 1.0 + (n**2 - s2) / n
    variance = (s2 * (s2 + n * (n + 1)) - 2 * n * s3 - n**3) / (n**2 * (n - 1))
    return float(mean), float(max(variance, 0.0))


def rotation_test(
    winners: Sequence,
    order: Sequence[float] | None = None,
    n_permutations: int = 2000,
    seed: int = 0,
) -> dict:
    """Runs test on a sequence of winners.

    ``winners`` must already be in time order unless ``order`` is given, in
    which case the sequence is sorted by it and ties are randomised.

    Returns the number of wins, distinct winners, observed and expected runs,
    a z-score, and ``p_value``: the share of shuffled sequences with at least
    as many runs as observed. A small p-value means the winner changes more
    often than chance, which is what rotation looks like.
    """
    labels = pd.factorize(np.asarray(winners, dtype=object))[0]
    n = labels.size
    counts = np.bincount(labels) if n else np.array([], dtype=int)
    result = {
        "n_wins": int(n),
        "n_winners": int(counts.size),
        "runs": np.nan,
        "expected_runs": np.nan,
        "z": np.nan,
        "p_value": np.nan,
    }
    if n < 2 or counts.size < 2:
        return result

    rng = np.random.default_rng(seed)
    if order is None:
        observed = float(count_runs(labels))
    else:
        observed = _runs_with_ties(labels, np.asarray(order, dtype=float), rng)

    mean, variance = expected_runs(counts)
    shuffled = np.empty(n_permutations)
    for i in range(n_permutations):
        shuffled[i] = count_runs(rng.permutation(labels))
    p_value = (1 + np.count_nonzero(shuffled >= observed - 1e-9)) / (n_permutations + 1)

    result.update(
        runs=observed,
        expected_runs=mean,
        z=(observed - mean) / np.sqrt(variance) if variance > 0 else np.nan,
        p_value=float(p_value),
    )
    return result


def _runs_with_ties(labels: np.ndarray, order: np.ndarray, rng, n_orderings: int = 50) -> float:
    """Runs in time order, averaged over random orderings of simultaneous tenders."""
    if np.unique(order).size == order.size:
        return float(count_runs(labels[np.argsort(order, kind="stable")]))
    total = 0
    for _ in range(n_orderings):
        jitter = rng.random(order.size)
        total += count_runs(labels[np.lexsort((jitter, order))])
    return total / n_orderings


def group_rotation(
    bids: pd.DataFrame,
    tenders: pd.DataFrame,
    members: frozenset,
    min_wins: int = MIN_WINS,
    seed: int = 0,
) -> dict:
    """Rotation test for one group of firms.

    Looks at tenders where at least two members bid and exactly one firm won.
    Wins by non-members are counted and reported but are not part of the
    sequence: the question is how the group shares out what it wins.
    """
    in_group = bids["firm"].isin(members)
    member_bids = bids.loc[in_group]
    per_tender = member_bids.groupby("tender_id")["firm"].size()
    joint = per_tender.index[per_tender >= 2]

    winners = bids.loc[bids["won"] & bids["tender_id"].isin(joint), ["tender_id", "firm"]]
    single = winners.groupby("tender_id")["firm"].transform("size") == 1
    winners = winners.loc[single]
    inside = winners.loc[winners["firm"].isin(members)].copy()
    inside["order"] = inside["tender_id"].map(tenders.set_index("tender_id")["order"])
    # A fixed row order, so that ties in time are broken the same way on
    # every run whatever order the bids arrived in.
    inside = inside.dropna(subset=["order"]).sort_values(["order", "tender_id"], kind="stable")

    out = {
        "n_joint_tenders": int(len(joint)),
        "n_decided": int(len(winners)),
        "n_member_wins": int(len(inside)),
        "inside_win_share": len(inside) / len(winners) if len(winners) else np.nan,
        "top_winner_share": np.nan,
    }
    if len(inside):
        out["top_winner_share"] = float(inside["firm"].value_counts(normalize=True).iloc[0])
    if len(inside) >= min_wins:
        out.update(
            rotation_test(inside["firm"].to_numpy(), order=inside["order"].to_numpy(), seed=seed)
        )
    else:
        out.update(rotation_test([]))
        out["n_wins"] = int(len(inside))
        out["n_winners"] = int(inside["firm"].nunique())
    return out
