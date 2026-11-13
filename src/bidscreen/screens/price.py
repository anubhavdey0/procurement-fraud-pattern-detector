"""Price screens: statistics of the distribution of bids within one tender.

These need the amount of every bid, losing bids included. They follow

* Abrantes-Metz, Froeb, Geweke and Taylor (2006), "A variance screen for
  collusion", Int. J. of Industrial Organization 24(3);
* Imhof, Karagok and Rutz (2018), "Screening for bid rigging: does it work?",
  J. of Competition Law and Economics 14(2);
* Huber and Imhof (2019), "Machine learning with screens for detecting
  bid-rigging cartels", Int. J. of Industrial Organization 65.

The idea behind all of them: when a cartel picks the winner in advance, the
other members submit cover bids. Cover bids sit close together and safely
above the designated winner. That squeezes the spread of bids, and it leaves
a gap between the lowest bid and the rest.

For a tender with sorted bids b1 <= b2 <= ... <= bn:

    cv     sd(b) / mean(b)                coefficient of variation
    spd    (bn - b1) / b1                 spread
    diffp  (b2 - b1) / b1                 gap between the two lowest bids
    rd     (b2 - b1) / sd(b2..bn)         relative distance
    skew   sample skewness of b
    kurt   sample excess kurtosis of b
    ks     Kolmogorov-Smirnov distance between b and a uniform spread on [b1, bn]

``expected`` records which direction the literature associates with collusion.
It is a prior to be tested, not a rule: the validation tables show cases where
a screen points the other way.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats


@dataclass(frozen=True)
class PriceScreen:
    key: str
    label: str
    expected: str  # "low" or "high" under collusion, per the literature
    min_bids: int
    why: str


PRICE_SCREENS: dict[str, PriceScreen] = {
    s.key: s
    for s in [
        PriceScreen("cv", "Coefficient of variation", "low", 2, "cover bids sit close together"),
        PriceScreen("spd", "Spread", "low", 2, "cover bids sit close together"),
        PriceScreen(
            "diffp",
            "Gap between two lowest bids",
            "high",
            2,
            "the designated winner is kept clear of the cover bids",
        ),
        PriceScreen(
            "rd",
            "Relative distance",
            "high",
            3,
            "the gap to the runner-up is large next to the spread of losing bids",
        ),
        PriceScreen(
            "skew", "Skewness", "low", 3, "cover bids bunch at the top, leaving a tail below"
        ),
        PriceScreen("kurt", "Kurtosis", "high", 4, "bids bunch around one value"),
        PriceScreen("ks", "Kolmogorov-Smirnov distance", "high", 2, "bids are not spread evenly"),
    ]
}


def bid_screens(values: np.ndarray) -> dict[str, float]:
    """All price screens for the bids of one tender."""
    b = np.sort(np.asarray(values, dtype=float))
    b = b[np.isfinite(b)]
    n = b.size
    out = {key: np.nan for key in PRICE_SCREENS}
    if n < 2 or b[0] <= 0:
        return out
    mean = b.mean()
    sd = b.std(ddof=1)
    out["cv"] = sd / mean
    out["spd"] = (b[-1] - b[0]) / b[0]
    out["diffp"] = (b[1] - b[0]) / b[0]
    if n >= 3:
        sd_losing = b[1:].std(ddof=1)
        if sd_losing > 0:
            out["rd"] = (b[1] - b[0]) / sd_losing
        if sd > 0:
            out["skew"] = float(stats.skew(b, bias=False))
    if n >= 4 and sd > 0:
        out["kurt"] = float(stats.kurtosis(b, bias=False))
    if b[-1] > b[0]:
        out["ks"] = _ks_uniform(b)
    return out


def _ks_uniform(sorted_bids: np.ndarray) -> float:
    """Kolmogorov-Smirnov distance between the bids and a uniform spread over
    their own range. Equal to ``scipy.stats.kstest(b, "uniform", args=(b1,
    bn - b1)).statistic``, written out because it is called once per tender."""
    n = sorted_bids.size
    u = (sorted_bids - sorted_bids[0]) / (sorted_bids[-1] - sorted_bids[0])
    steps = np.arange(1, n + 1) / n
    return float(max(np.max(steps - u), np.max(u - (steps - 1.0 / n))))


def tender_price_screens(bids: pd.DataFrame) -> pd.DataFrame:
    """Price screens for every tender that has at least two priced bids.

    Returns a frame indexed by ``tender_id`` with one column per screen plus
    ``n_bids``. Tenders without bid amounts are left out.
    """
    priced = bids.loc[bids["bid_value"].notna(), ["tender_id", "bid_value"]]
    rows = {}
    for tender_id, values in priced.groupby("tender_id", sort=False)["bid_value"]:
        array = values.to_numpy(dtype=float)
        if array.size < 2:
            continue
        row = bid_screens(array)
        row["n_bids"] = int(array.size)
        rows[tender_id] = row
    columns = ["n_bids", *PRICE_SCREENS]
    if not rows:
        return pd.DataFrame(columns=columns).rename_axis("tender_id")
    return pd.DataFrame.from_dict(rows, orient="index")[columns].rename_axis("tender_id")


def oriented(screens: pd.DataFrame) -> pd.DataFrame:
    """Flip each screen so that a larger value always means "more as the
    literature expects under collusion". Used for scoring and for AUC."""
    out = pd.DataFrame(index=screens.index)
    for key, screen in PRICE_SCREENS.items():
        if key in screens.columns:
            out[key] = -screens[key] if screen.expected == "low" else screens[key]
    return out
