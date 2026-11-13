"""The two tables every loader produces and every screen consumes.

``tenders`` has one row per tender:

    tender_id    str    unique within the market
    segment      str    stratum used by the null model (a buyer, or "all")
    buyer        str    procuring body, raw name (pseudonymised before export)
    order        float  sortable position in time (a timestamp or a rank)
    date         datetime64, NaT when the source gives no calendar date
    estimate     float  buyer's pre-tender estimate, NaN when unknown
    award_value  float  awarded value, NaN when unknown or split across awards
    collusive    object True / False where a court or authority labelled the
                        tender, otherwise None

``bids`` has one row per (tender, firm):

    tender_id      str
    firm           str    firm key (normalised name or source id)
    bid_value      float  NaN when the source publishes only who bid
    won            bool
    cartel_member  object True / False where labelled, otherwise None
    cartel         object name of the documented cartel, where the source has one

A loader fills what its source has and leaves the rest missing. Screens check
for the columns they need and say so when they cannot run.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

TENDER_COLUMNS = [
    "tender_id",
    "segment",
    "buyer",
    "order",
    "date",
    "estimate",
    "award_value",
    "collusive",
]
BID_COLUMNS = ["tender_id", "firm", "bid_value", "won", "cartel_member", "cartel"]


@dataclass
class Market:
    """One procurement market: a set of tenders and the bids placed on them."""

    name: str
    tenders: pd.DataFrame
    bids: pd.DataFrame
    title: str = ""
    description: str = ""
    source: str = ""
    currency: str | None = None
    lowest_bid_wins: bool = True
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.tenders = _conform(self.tenders, TENDER_COLUMNS)
        self.bids = _conform(self.bids, BID_COLUMNS)
        self.tenders["tender_id"] = self.tenders["tender_id"].astype(str)
        self.bids["tender_id"] = self.bids["tender_id"].astype(str)
        self.bids["firm"] = self.bids["firm"].astype(str)
        self.bids["won"] = self.bids["won"].fillna(False).astype(bool)
        if self.tenders["tender_id"].duplicated().any():
            raise ValueError(f"{self.name}: duplicate tender_id in tenders")
        # Sources without bidder identities leave ``firm`` empty on every row.
        dupes = self.bids.duplicated(["tender_id", "firm"]) & (self.bids["firm"] != "")
        if dupes.any():
            raise ValueError(
                f"{self.name}: {int(dupes.sum())} duplicate (tender, firm) rows in bids"
            )
        unknown = ~self.bids["tender_id"].isin(self.tenders["tender_id"])
        if unknown.any():
            raise ValueError(f"{self.name}: {int(unknown.sum())} bids reference unknown tenders")

    @property
    def has_prices(self) -> bool:
        """True when losing bids carry amounts, so price screens can run."""
        return bool(self.bids["bid_value"].notna().any())

    @property
    def has_firms(self) -> bool:
        """True when bidders are identified, so the co-bidding graph can be built."""
        return bool((self.bids["firm"] != "").any())

    @property
    def has_tender_labels(self) -> bool:
        return bool(self.tenders["collusive"].notna().any())

    @property
    def has_firm_labels(self) -> bool:
        return bool(self.bids["cartel_member"].notna().any())

    def summary(self) -> dict:
        bids, tenders = self.bids, self.tenders
        per_tender = bids.groupby("tender_id").size()
        return {
            "market": self.name,
            "tenders": int(len(tenders)),
            "tenders_with_bidders": int(per_tender.size),
            "bids": int(len(bids)),
            "firms": int(bids.loc[bids["firm"] != "", "firm"].nunique()),
            "median_bidders": float(per_tender.median()) if len(per_tender) else float("nan"),
            "tenders_with_winner": int(bids.loc[bids["won"], "tender_id"].nunique()),
            "has_prices": self.has_prices,
            "labelled_collusive_tenders": int((tenders["collusive"] == True).sum()),  # noqa: E712
        }


def _conform(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Return a copy with every expected column present, in the expected order."""
    out = frame.copy()
    for col in columns:
        if col not in out.columns:
            out[col] = None
    extra = [c for c in out.columns if c not in columns]
    return out[columns + extra].reset_index(drop=True)
