"""Run every screen on a market and assemble leads for review.

A lead is a group of firms on which more than one screen fired. It is a
reason to open the tender files, nothing more. Every lead carries the numbers
behind each screen and a list of ordinary explanations to rule out first.

Screens applied to each group of co-bidders:

    closed    the group is much more exclusive than reshuffled markets allow
              and at least ``exclusivity_min`` of its co-bidding is internal
    rotation  members take turns winning more often than chance
    cover     a member keeps bidding next to the others and keeps losing
    price     the group's awards sit closer to the estimate than other
              contested tenders from the same buyers

The rotation, cover and price screens each run one test per group, so their
p-values are adjusted for the number of groups tested (Benjamini-Hochberg).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from bidscreen import graph
from bidscreen.model import Market
from bidscreen.screens import cover, pricing, rotation
from bidscreen.screens.price import tender_price_screens

SCREENS = ["closed", "rotation", "cover", "price"]

SCREEN_LABELS = {
    "closed": "Closed group",
    "rotation": "Winner rotation",
    "cover": "Persistent losing bidder",
    "price": "Awards near the estimate",
}

# What a reviewer should rule out before reading anything into a screen.
RULE_OUT = {
    "closed": [
        "A small local market: few contractors are registered, eligible or near enough to bid.",
        "A specialised trade or contractor class that only these firms hold.",
        "Related firms that are openly part of one business group.",
    ],
    "rotation": [
        "Capacity limits: a firm busy with one contract bids high on the next.",
        "Lots awarded together under a rule that caps awards per bidder.",
    ],
    "cover": [
        "A small or new firm that bids often and is simply not competitive.",
        "Bids rejected at the technical stage for paperwork reasons.",
    ],
    "price": [
        "An estimate that is out of date, so honest bids land at or above it.",
        "A floor on bids below the estimate that piles awards at the same ratio.",
        "Work that is harder than the buyer's schedule of rates assumes.",
    ],
}


@dataclass
class ScreenConfig:
    """Every threshold in one place. All of them are judgement calls."""

    min_joint: int = 3  # joint tenders before two firms can be linked
    fdr: float = 0.01  # false discovery rate for co-bidding links
    min_group: int = 3
    max_group: int = 25
    n_null: int = 20  # reshuffled markets for the exclusivity test
    exclusivity_min: float = 0.25  # share of co-bidding that must be internal
    alpha: float = 0.05  # level for the exclusivity test
    outcome_fdr: float = 0.10  # false discovery rate for outcome screens
    rotation_min_wins: int = 8
    cover_min_bids: int = 10
    price_min_awards: int = 5
    min_screens: int = 2  # screens that must fire for a group to be a lead
    seed: int = 0


@dataclass
class ScreenResult:
    market: Market
    config: ScreenConfig
    links: pd.DataFrame
    groups: pd.DataFrame
    firms: pd.DataFrame
    price: pd.DataFrame
    summary: dict = field(default_factory=dict)

    @property
    def leads(self) -> pd.DataFrame:
        """Groups on which at least ``min_screens`` screens fired."""
        if self.groups.empty:
            return self.groups
        return self.groups.loc[self.groups["n_screens"] >= self.config.min_screens]


def screen_market(market: Market, config: ScreenConfig | None = None) -> ScreenResult:
    """Run all screens the market's data supports."""
    config = config or ScreenConfig()
    bids, tenders = market.bids, market.tenders

    price = tender_price_screens(bids) if market.has_prices else pd.DataFrame()
    summary = {**market.summary(), "config": asdict(config)}

    if not market.has_firms:
        summary["note"] = "bidders are not identified, so no group screens were run"
        return ScreenResult(
            market, config, pd.DataFrame(), _empty_groups(), pd.DataFrame(), price, summary
        )

    pairs = graph.cobid_pairs(bids, tenders, min_joint=config.min_joint)
    links = graph.significant_links(pairs, min_joint=config.min_joint, fdr=config.fdr)
    network = graph.cobid_network(links)
    found = graph.find_groups(network, min_size=config.min_group, max_size=config.max_group)
    groups = graph.group_metrics(bids, found)

    null = graph.exclusivity_null(bids, tenders, found, config.n_null, config.seed)
    groups["null_exclusivity"] = null.mean(axis=1) if len(found) else []
    groups["p_exclusivity"] = (
        graph.exclusivity_p_values(groups["exclusivity"].to_numpy(), null) if len(found) else []
    )

    expectations = cover.win_expectations(bids)
    priced = pricing.priced_tenders(bids, tenders)
    context = _Context(bids, tenders, expectations, priced, config)
    details = [context.describe(members) for members in groups["members"]]
    groups = pd.concat([groups, pd.DataFrame(details, index=groups.index)], axis=1)
    groups = _flag(groups, config)

    summary.update(
        cobid_pairs=int(pairs.attrs.get("n_cobid_pairs", len(pairs))),
        candidate_pairs=int(len(pairs)),
        significant_links=int(len(links)),
        firms_linked=int(network.number_of_nodes()),
        groups=int(len(groups)),
        leads=int((groups["n_screens"] >= config.min_screens).sum()) if len(groups) else 0,
        screens_fired={s: int(groups[f"flag_{s}"].sum()) if len(groups) else 0 for s in SCREENS},
        priced_awards=int(len(priced)),
    )
    return ScreenResult(
        market, config, links, groups, _firm_table(bids, expectations, groups), price, summary
    )


class _Context:
    """Tables shared by every group, computed once.

    Each group only concerns the tenders its members bid on. Row positions are
    indexed by firm and by tender so a group's slice of the market can be cut
    out without scanning every bid.
    """

    def __init__(self, bids, tenders, expectations, priced, config):
        self.bids = bids.reset_index(drop=True)
        self.tenders = tenders
        self.expectations = expectations.reset_index(drop=True)
        self.priced = priced
        self.config = config
        known = self.bids.loc[self.bids["firm"] != ""]
        self.n_bidders = known.groupby("tender_id")["firm"].size()
        indexed = tenders.set_index("tender_id")
        self.segment = indexed["segment"]
        self.date = indexed["date"]
        self.order = indexed[["order"]].reset_index()
        self._rows_by_firm = self.bids.groupby("firm").indices
        self._rows_by_tender = self.bids.groupby("tender_id").indices
        self._expect_by_tender = self.expectations.groupby("tender_id").indices

    def _slice(self, members: frozenset) -> tuple[pd.DataFrame, pd.DataFrame]:
        """All bids, and all win expectations, on tenders a member bid on."""
        # Sorted: set order changes from one Python process to the next, and
        # row order must not change the result.
        firm_rows = [self._rows_by_firm[f] for f in sorted(members) if f in self._rows_by_firm]
        if not firm_rows:
            return self.bids.iloc[:0], self.expectations.iloc[:0]
        touched = self.bids["tender_id"].to_numpy()[np.concatenate(firm_rows)]
        tender_ids = pd.unique(touched)
        rows = np.concatenate([self._rows_by_tender[t] for t in tender_ids])
        expect_rows = [self._expect_by_tender[t] for t in tender_ids if t in self._expect_by_tender]
        expect = (
            self.expectations.iloc[np.concatenate(expect_rows)]
            if expect_rows
            else self.expectations.iloc[:0]
        )
        return self.bids.iloc[rows], expect

    def describe(self, members: frozenset) -> dict:
        config = self.config
        bids, expectations = self._slice(members)
        member_bids = bids.loc[bids["firm"].isin(members)]
        per_tender = member_bids.groupby("tender_id")["firm"].size()
        joint = per_tender.loc[per_tender >= 2]
        closed = joint.loc[joint == self.n_bidders.reindex(joint.index)]
        segments = self.segment.reindex(joint.index).value_counts()
        dates = pd.to_datetime(self.date.reindex(joint.index)).dropna()
        tenders = self.order.loc[self.order["tender_id"].isin(joint.index)]

        out = {
            "n_closed_tenders": int(len(closed)),
            "closed_share": len(closed) / len(joint) if len(joint) else np.nan,
            "n_segments": int(len(segments)),
            "top_segment": segments.index[0] if len(segments) else None,
            "top_segment_share": float(segments.iloc[0] / segments.sum())
            if len(segments)
            else np.nan,
            "first_date": dates.min() if len(dates) else pd.NaT,
            "last_date": dates.max() if len(dates) else pd.NaT,
        }
        out.update(
            rotation.group_rotation(bids, tenders, members, config.rotation_min_wins, config.seed)
        )
        out["rotation_p"] = out.pop("p_value")
        out["rotation_z"] = out.pop("z")

        losers = cover.group_cover(bids, members, config.cover_min_bids, expectations=expectations)
        table = losers["loser_table"]
        out["n_members_tested"] = losers["n_members_tested"]
        out["cover_p"] = losers["min_p_low"]
        out["cover_firm"] = table["firm"].iloc[0] if len(table) else None
        out["cover_bids"] = int(table["n_bids"].iloc[0]) if len(table) else 0
        out["cover_wins"] = int(table["wins"].iloc[0]) if len(table) else 0
        out["cover_expected"] = float(table["expected_wins"].iloc[0]) if len(table) else np.nan

        out.update(
            pricing.group_relative_price(
                bids, self.tenders, members, priced=self.priced, min_awards=config.price_min_awards
            )
        )
        return out


def _flag(groups: pd.DataFrame, config: ScreenConfig) -> pd.DataFrame:
    if groups.empty:
        return _empty_groups()
    groups = groups.copy()
    # The cover test picks the most extreme member of each group, so the
    # p-value is first corrected for the number of members tested.
    cover_p = np.minimum(groups["cover_p"] * groups["n_members_tested"].clip(lower=1), 1.0)
    groups["rotation_q"] = _adjust(groups["rotation_p"])
    groups["cover_q"] = _adjust(cover_p)
    groups["price_q"] = _adjust(groups["price_p_value"])

    groups["flag_closed"] = (groups["p_exclusivity"] <= config.alpha) & (
        groups["exclusivity"] >= config.exclusivity_min
    )
    groups["flag_rotation"] = (groups["rotation_q"] <= config.outcome_fdr) & (
        groups["rotation_z"] > 0
    )
    groups["flag_cover"] = groups["cover_q"] <= config.outcome_fdr
    groups["flag_price"] = groups["price_q"] <= config.outcome_fdr
    flags = groups[[f"flag_{s}" for s in SCREENS]].fillna(False).astype(bool)
    groups[flags.columns] = flags
    groups["n_screens"] = flags.sum(axis=1).astype(int)
    groups["screens"] = [[s for s in SCREENS if row[f"flag_{s}"]] for _, row in flags.iterrows()]

    groups = groups.sort_values(
        ["n_screens", "flag_closed", "exclusivity"], ascending=[False, False, False]
    ).reset_index(drop=True)
    width = max(3, len(str(len(groups))))
    groups.insert(0, "group_id", [f"G{i:0{width}d}" for i in range(1, len(groups) + 1)])
    return groups


def _adjust(p_values: pd.Series) -> pd.Series:
    """Benjamini-Hochberg across the groups that could be tested."""
    out = pd.Series(np.nan, index=p_values.index)
    tested = p_values.notna()
    if tested.any():
        out.loc[tested] = graph.benjamini_hochberg(p_values.loc[tested].to_numpy(dtype=float))
    return out


def _firm_table(bids, expectations, groups) -> pd.DataFrame:
    known = bids.loc[bids["firm"] != ""]
    firms = known.groupby("firm").agg(n_bids=("tender_id", "size"), wins=("won", "sum"))
    decided = expectations.groupby("firm").agg(
        decided_bids=("tender_id", "size"), expected_wins=("p_win", "sum")
    )
    firms = firms.join(decided, how="left").fillna({"decided_bids": 0, "expected_wins": 0.0})
    membership: dict[str, list[str]] = {}
    if len(groups):
        for group_id, members in zip(groups["group_id"], groups["members"], strict=True):
            for firm in members:
                membership.setdefault(firm, []).append(group_id)
    firms["groups"] = [membership.get(f, []) for f in firms.index]
    return firms.reset_index().sort_values("n_bids", ascending=False).reset_index(drop=True)


def _empty_groups() -> pd.DataFrame:
    columns = [
        "group_id",
        *graph.GROUP_COLUMNS,
        "null_exclusivity",
        "p_exclusivity",
        *[f"flag_{s}" for s in SCREENS],
        "n_screens",
        "screens",
    ]
    return pd.DataFrame(columns=columns)


def lead_tenders(result: ScreenResult) -> pd.DataFrame:
    """The tenders behind each lead: those where at least two members bid."""
    rows = []
    bids = result.market.bids
    for group_id, members in zip(result.leads["group_id"], result.leads["members"], strict=True):
        member_bids = bids.loc[bids["firm"].isin(members)]
        per_tender = member_bids.groupby("tender_id")["firm"].size()
        for tender_id, n_members in per_tender.loc[per_tender >= 2].items():
            rows.append({"group_id": group_id, "tender_id": tender_id, "n_members": int(n_members)})
    return pd.DataFrame(rows, columns=["group_id", "tender_id", "n_members"])
