"""Bid data from six documented bid-rigging cases.

These are the ground truth. Each file holds every bid in a set of tenders,
with a flag for the tenders and bidders that a competition authority or court
found to be part of a cartel. The files were assembled and published with

    Garcia Rodriguez, Rodriguez-Montequin, Ballesteros-Perez, Love and Signor
    (2022), "Collusion detection in public procurement auctions with machine
    learning algorithms", Automation in Construction 133, 104047.

The files are not redistributed here; ``bidscreen fetch`` downloads them.

Firms appear only as the numeric ids the dataset already uses. The one column
that carries company names (in the Japanese file) is dropped on load and is
never written anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from bidscreen.model import Market

SOURCE = (
    "Garcia Rodriguez et al. (2022), Automation in Construction 133, 104047 "
    "(doi:10.1016/j.autcon.2021.104047)"
)


@dataclass(frozen=True)
class Case:
    key: str
    filename: str
    title: str
    description: str
    currency: str
    date_kind: str  # "epoch" seconds, "year", "ordinal" day count, or "none"
    has_firms: bool
    lowest_bid_wins: bool
    estimate_column: str | None = None


LABELLED_CASES: dict[str, Case] = {
    case.key: case
    for case in [
        Case(
            key="switzerland_ticino",
            filename="6.Ticino.xlsx",
            title="Switzerland: Ticino",
            description="Road construction cartel in the canton of Ticino, sanctioned by the "
            "Swiss Competition Commission.",
            currency="CHF",
            date_kind="epoch",
            has_firms=False,
            lowest_bid_wins=True,
        ),
        Case(
            key="switzerland_gr_sg",
            filename="3.GR_and_See-Gaster.xlsx",
            title="Switzerland: Graubunden and See-Gaster",
            description="Construction cartels in Graubunden and See-Gaster, sanctioned by the "
            "Swiss Competition Commission.",
            currency="CHF",
            date_kind="ordinal",
            has_firms=False,
            lowest_bid_wins=True,
        ),
        Case(
            key="japan",
            filename="5.Japan.xlsx",
            title="Japan: Okinawa",
            description="Building works in Okinawa before and after the Japan Fair Trade "
            "Commission inspection.",
            currency="JPY",
            date_kind="epoch",
            has_firms=True,
            lowest_bid_wins=True,
            estimate_column="Pre-Tender Estimate (PTE)",
        ),
        Case(
            key="brazil",
            filename="2.Brazil.xlsx",
            title="Brazil: Petrobras",
            description="Infrastructure tenders examined in Operation Car Wash.",
            currency="BRL",
            date_kind="epoch",
            has_firms=True,
            lowest_bid_wins=True,
            estimate_column="Pre-Tender Estimate (PTE)",
        ),
        Case(
            key="italy",
            filename="4.Italy.xlsx",
            title="Italy: Turin",
            description="Road works awarded by average-bid auctions, where the winner is the "
            "bid closest to a trimmed mean and not the lowest bid.",
            currency="EUR",
            date_kind="none",
            has_firms=True,
            lowest_bid_wins=False,
            estimate_column="Pre-Tender Estimate (PTE)",
        ),
        Case(
            key="usa",
            filename="7.America.xlsx",
            title="USA: Ohio school milk",
            description="School milk contracts in Ohio, 1980 to 1990, with the Cincinnati "
            "dairy cartel.",
            currency="USD",
            date_kind="year",
            has_firms=True,
            lowest_bid_wins=True,
        ),
    ]
}

# Columns that must never be carried forward.
_DROP_COLUMNS = ["Name competitors"]


def load_labelled(key: str, raw_dir: Path | str = "data/raw/labelled") -> Market:
    """Load one documented cartel case as a :class:`Market`."""
    if key not in LABELLED_CASES:
        raise KeyError(f"unknown case {key!r}; expected one of {sorted(LABELLED_CASES)}")
    case = LABELLED_CASES[key]
    path = Path(raw_dir) / case.filename
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing. Run `bidscreen fetch labelled` first.")
    raw = pd.read_excel(path).drop(columns=_DROP_COLUMNS, errors="ignore")
    return _to_market(case, raw)


def _to_market(case: Case, raw: pd.DataFrame) -> Market:
    notes: list[str] = []
    raw = raw.copy()
    raw["tender_id"] = raw["Tender"].astype(int).astype(str)

    if case.has_firms:
        raw["firm"] = raw["Competitors"].astype(int).astype(str)
        before = len(raw)
        # A firm listed twice in one tender keeps its lowest bid.
        raw = raw.sort_values("Bid_value").drop_duplicates(["tender_id", "firm"], keep="first")
        if len(raw) < before:
            notes.append(f"dropped {before - len(raw)} repeated (tender, firm) rows")
    else:
        raw["firm"] = ""
        notes.append("the source does not identify bidders, so only price screens can run")

    member_col = (
        "Collusive_competitor_original"
        if "Collusive_competitor_original" in raw.columns
        else "Collusive_competitor"
    )
    bids = pd.DataFrame(
        {
            "tender_id": raw["tender_id"],
            "firm": raw["firm"],
            "bid_value": raw["Bid_value"].astype(float),
            "won": raw["Winner"].fillna(0).astype(int) == 1,
            "cartel_member": raw[member_col].astype(int) == 1,
            "cartel": None,
        }
    )

    grouped = raw.groupby("tender_id", sort=False)
    tenders = pd.DataFrame({"tender_id": list(grouped.groups.keys())})
    tenders["segment"] = "all"
    tenders["buyer"] = case.key
    order, date = _order_and_date(case, grouped)
    tenders["order"] = tenders["tender_id"].map(order)
    tenders["date"] = tenders["tender_id"].map(date) if date is not None else pd.NaT
    if case.estimate_column and case.estimate_column in raw.columns:
        tenders["estimate"] = tenders["tender_id"].map(grouped[case.estimate_column].first())
    else:
        tenders["estimate"] = np.nan
    winning = raw.loc[raw["Winner"] == 1].groupby("tender_id")["Bid_value"].min()
    tenders["award_value"] = tenders["tender_id"].map(winning)
    # The published label is constant within a tender.
    tenders["collusive"] = tenders["tender_id"].map(grouped["Collusive_competitor"].max() == 1)

    if not case.lowest_bid_wins:
        notes.append("the award rule is not lowest bid, so winner-based screens do not apply")
    if case.date_kind == "none":
        notes.append("the source has no dates, so the rotation screen cannot run")

    return Market(
        name=case.key,
        title=case.title,
        tenders=tenders,
        bids=bids.reset_index(drop=True),
        description=f"{case.title}. {case.description}",
        source=SOURCE,
        currency=case.currency,
        lowest_bid_wins=case.lowest_bid_wins,
        notes=notes,
    )


def _order_and_date(case: Case, grouped) -> tuple[pd.Series, pd.Series | None]:
    """A sortable position for every tender, and a calendar date where known."""
    if case.date_kind == "none":
        first = grouped["Tender"].first().astype(float)
        return first, None
    value = grouped["Date"].first().astype(float)
    if case.date_kind == "epoch":
        return value, pd.to_datetime(value, unit="s")
    if case.date_kind == "year":
        return value, pd.to_datetime(value.astype(int).astype(str), format="%Y")
    return value, None  # ordinal day counts with an undocumented origin
