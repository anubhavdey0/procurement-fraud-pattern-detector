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

Tenders opened at the same moment have no order between them. For those, the
statistic is the number of runs to expect when each batch of simultaneous
tenders is put in random order, worked out exactly rather than by sampling.
Every shuffled sequence is scored the same way, so batches do not tilt the
test either way.

The number of runs is a whole number and many shuffles tie with the observed
value, which makes an ordinary permutation p-value conservative: at a nominal
5% it fires well under 5% of the time. The p-value here is the mid-p, which
counts ties with the observed value as half (Lancaster 1961). Its error rate
is close to the nominal level on average, at the price of not being bounded
by it in every case.

Limits: the test needs the tenders in time order, and it needs enough wins to
say anything (seven alternating wins between two firms is the least that
reaches p < 0.05).
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
    which case the sequence is sorted by it and tenders with equal ``order``
    form a batch with no order inside it.

    Returns the number of wins, distinct winners, observed and expected runs,
    a z-score, and ``p_value``: the mid-p share of shuffled sequences with
    more runs than observed. A small p-value means the winner changes more
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

    if order is None:
        batch = np.arange(n)
    else:
        sort = np.argsort(np.asarray(order, dtype=float), kind="stable")
        labels = labels[sort]
        batch = np.unique(np.asarray(order, dtype=float)[sort], return_inverse=True)[1]

    rng = np.random.default_rng(seed)
    observed = float(batch_runs(labels[None, :], batch, counts.size)[0])
    shuffled = batch_runs(
        rng.permuted(np.tile(labels, (n_permutations, 1)), axis=1), batch, counts.size
    )
    tied = np.isclose(shuffled, observed, rtol=0.0, atol=1e-9)
    above = np.count_nonzero((shuffled > observed) & ~tied)
    # The observed sequence is one of the n_permutations + 1 equally likely
    # ones and ties with itself, so it adds a half.
    p_value = (above + 0.5 * (np.count_nonzero(tied) + 1)) / (n_permutations + 1)

    mean, variance = expected_runs(counts)
    if batch[-1] + 1 < n:
        # Batches narrow the spread of the statistic, so take it from the shuffles.
        variance = float(np.var(shuffled))
    result.update(
        runs=observed,
        expected_runs=mean,
        z=(observed - mean) / np.sqrt(variance) if variance > 0 else np.nan,
        p_value=float(p_value),
    )
    return result


def batch_runs(labels: np.ndarray, batch: np.ndarray, n_labels: int) -> np.ndarray:
    """Expected number of runs in each row of ``labels`` when the positions
    sharing a ``batch`` number are put in random order.

    ``batch`` numbers positions 0, 1, ... and must not decrease. Inside a
    batch of size b, two neighbours differ with probability 1 minus the share
    of ordered pairs with the same label. Across the boundary between two
    batches, the neighbours are one random member of each. Without batches
    this is the plain count of runs.
    """
    labels = np.atleast_2d(labels)
    rows, n = labels.shape
    if batch[-1] + 1 == n:
        return 1.0 + np.count_nonzero(labels[:, 1:] != labels[:, :-1], axis=1)
    n_batches = int(batch[-1]) + 1
    size = np.bincount(batch, minlength=n_batches).astype(float)
    out = np.empty(rows)
    step = max(1, 2_000_000 // max(n_batches * n_labels, 1))
    for start in range(0, rows, step):
        block = labels[start : start + step]
        k = block.shape[0]
        flat = (np.arange(k)[:, None] * n_batches + batch[None, :]) * n_labels + block
        counts = np.bincount(flat.ravel(), minlength=k * n_batches * n_labels)
        counts = counts.reshape(k, n_batches, n_labels).astype(float)
        within = (size - 1).sum() - ((counts * (counts - 1)).sum(axis=2) / size).sum(axis=1)
        share = counts / size[None, :, None]
        across = (1.0 - (share[:, :-1] * share[:, 1:]).sum(axis=2)).sum(axis=1)
        out[start : start + k] = 1.0 + within + across
    return out


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
