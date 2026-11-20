"""Write the leads report: one self-contained HTML page plus CSV tables.

Nothing in the output carries a real name. Firms, tenders and buyers are
replaced by keyed labels before anything is rendered, dates are cut to the
month, and the finished page is searched for every real identifier before it
is written. If one is found the report is not written at all.
"""

from __future__ import annotations

import inspect
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from jinja2 import Environment, PackageLoader, select_autoescape
from markupsafe import Markup

from bidscreen import __version__, charts
from bidscreen import leads as leads_module
from bidscreen.anonymize import Pseudonymizer, assert_no_leak
from bidscreen.leads import RULE_OUT, SCREEN_LABELS, SCREENS, ScreenResult
from bidscreen.screens import price as price_module
from bidscreen.screens.price import PRICE_SCREENS
from bidscreen.screens.pricing import NEAR_ESTIMATE, priced_tenders
from bidscreen.validate import BENCHMARK_CV, BENCHMARK_RD

MAX_TENDERS_SHOWN = 40
CASE_TITLES = {
    "switzerland_ticino": "Switzerland: Ticino",
    "switzerland_gr_sg": "Switzerland: Graubunden and See-Gaster",
    "japan": "Japan: Okinawa",
    "brazil": "Brazil: Petrobras",
    "italy": "Italy: Turin",
    "usa": "USA: Ohio school milk",
}

REFERENCES = [
    "Abrantes-Metz, Froeb, Geweke and Taylor (2006). A variance screen for collusion. "
    "International Journal of Industrial Organization 24(3).",
    "Garcia Rodriguez, Rodriguez-Montequin, Ballesteros-Perez, Love and Signor (2022). "
    "Collusion detection in public procurement auctions with machine learning algorithms. "
    "Automation in Construction 133.",
    "Huber and Imhof (2019). Machine learning with screens for detecting bid-rigging cartels. "
    "International Journal of Industrial Organization 65.",
    "Imhof, Karagok and Rutz (2018). Screening for bid rigging: does it work? "
    "Journal of Competition Law and Economics 14(2).",
    "OECD (2009). Guidelines for fighting bid rigging in public procurement.",
    "Onnela, Saramaki, Kertesz and Kaski (2005). Intensity and coherence of motifs in "
    "weighted complex networks. Physical Review E 71.",
    "Toth, Fazekas, Czibik and Toth (2014). Toolkit for detecting collusive bidding in "
    "public procurement. Corruption Research Center Budapest.",
    "Wachs and Kertesz (2019). A network approach to cartel detection in public auction "
    "markets. Scientific Reports 9, 10818.",
]


def build_report(
    result: ScreenResult,
    out_dir: Path | str,
    key: bytes,
    validation: dict[str, pd.DataFrame] | None = None,
    title: str | None = None,
) -> Path:
    """Render the report into ``out_dir`` and return the path of the page."""
    out_dir = Path(out_dir)
    (out_dir / "figures").mkdir(parents=True, exist_ok=True)
    market = result.market
    names = _fit_labels(result, key)

    figures: dict[str, str] = {}
    leads = [_lead_view(result, row, names, figures) for _, row in result.leads.iterrows()]
    groups_svg, group_rows = _groups_view(result, figures)
    price = _price_view(result, figures)
    tight = _tender_view(result, names)
    checks = _validation_view(validation, figures)

    environment = Environment(
        loader=PackageLoader("bidscreen", "templates"),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    environment.filters.update(pct=_pct, num=_num, f1=_f1, f2=_f2, f3=_f3, pval=_pval)
    page = environment.get_template("report.html").render(
        title=title or f"Leads for review: {market.title or market.name}",
        market=market,
        summary=result.summary,
        config=result.config,
        tiles=_tiles(result),
        coverage=_coverage(result),
        leads=leads,
        groups_svg=Markup(groups_svg) if groups_svg else None,
        group_rows=group_rows,
        price=price,
        tight=tight,
        checks=checks,
        screen_labels=SCREEN_LABELS,
        references=REFERENCES,
        viz_css=Markup(charts.VIZ_CSS),
        themes=charts.THEMES,
        version=__version__,
        generated=date.today().strftime("%d %B %Y"),
    )

    assert_no_leak(page, _real_identifiers(result), allow=fixed_wording(market))
    path = out_dir / "report.html"
    path.write_text(page, encoding="utf-8")
    for name, svg in figures.items():
        for theme in charts.THEMES:
            target = out_dir / "figures" / f"{name}-{theme}.svg"
            target.write_text(charts.standalone(svg, theme), encoding="utf-8")
    _write_tables(result, names, out_dir)
    return path


# --------------------------------------------------------------------------
# Labels
# --------------------------------------------------------------------------


def _fit_labels(result: ScreenResult, key: bytes) -> Pseudonymizer:
    market = result.market
    names = Pseudonymizer(key)
    names.fit("firm", market.bids["firm"])
    names.fit("tender", market.tenders["tender_id"])
    names.fit("buyer", market.tenders["buyer"])
    return names


def fixed_wording(market, *extra: str) -> str:
    """The output's own wording: the template, captions and labels written in
    this package. An identifier that occurs here is an ordinary phrase, not a
    name, so the leak check lets it pass."""
    loader = PackageLoader("bidscreen", "templates")
    return "\n".join(
        [
            loader.get_source(Environment(), "report.html")[0],
            inspect.getsource(sys.modules[__name__]),
            inspect.getsource(charts),
            inspect.getsource(leads_module),
            inspect.getsource(price_module),
            market.description,
            market.source,
            *market.notes,
            *extra,
        ]
    )


def _real_identifiers(result: ScreenResult) -> set[str]:
    """Everything that must not appear in the page. Synthetic markets are
    exempt: their names are invented and are useful to see in a demo."""
    market = result.market
    if market.name == "synthetic":
        return set()
    firms = set(market.bids["firm"].astype(str))
    tenders = set(market.tenders["tender_id"].astype(str))
    buyers = set(market.tenders["buyer"].astype(str))
    # Numeric ids from the labelled cases are not names and would match
    # ordinary numbers on the page.
    return {v for v in firms | tenders | buyers if not v.replace(".", "").isdigit()}


# --------------------------------------------------------------------------
# Page sections
# --------------------------------------------------------------------------


def _tiles(result: ScreenResult) -> list[dict]:
    s = result.summary
    return [
        {"label": "Tenders with a bidder list", "value": _num(s.get("tenders_with_bidders", 0))},
        {"label": "Distinct bidders", "value": _num(s.get("firms", 0))},
        {"label": "Pairs that ever bid together", "value": _num(s.get("cobid_pairs", 0))},
        {"label": "Co-bidding groups found", "value": _num(s.get("groups", 0))},
        {"label": "Leads for review", "value": _num(s.get("leads", 0))},
    ]


def _coverage(result: ScreenResult) -> dict:
    market, s = result.market, result.summary
    return {
        "tenders": s.get("tenders", 0),
        "with_bidders": s.get("tenders_with_bidders", 0),
        "with_winner": s.get("tenders_with_winner", 0),
        "priced": s.get("priced_awards", 0),
        "has_prices": market.has_prices,
        "notes": market.notes,
    }


def _lead_view(result: ScreenResult, row: pd.Series, names: Pseudonymizer, figures: dict) -> dict:
    market, config = result.market, result.config
    members = row["members"]
    labels = sorted(names.labels("firm", members))
    fired = set(row["screens"])

    screens = [
        {
            "key": key,
            "label": SCREEN_LABELS[key],
            "fired": key in fired,
            "text": _screen_text(key, row, names, config),
        }
        for key in SCREENS
    ]
    rule_out = [item for key in SCREENS if key in fired for item in RULE_OUT[key]]
    svg, tender_rows, shown, graph = _lead_figure(market, row, names)
    figures.setdefault("lead-example", svg)

    return {
        "id": row["group_id"],
        "members": labels,
        "size": int(row["size"]),
        "n_screens": int(row["n_screens"]),
        "fired_labels": [SCREEN_LABELS[k] for k in SCREENS if k in fired],
        "n_joint": int(row["n_joint_tenders"]),
        "n_closed": int(row["n_closed_tenders"]),
        "closed_share": row["closed_share"],
        "n_wins": int(row["n_member_wins"]),
        "n_decided": int(row["n_decided"]),
        "n_buyers": int(row["n_segments"]),
        "period": _period(row["first_date"], row["last_date"]),
        "screens": screens,
        "rule_out": rule_out,
        "svg": Markup(svg),
        "tenders": tender_rows,
        "tenders_shown": shown,
        "graph": graph,
    }


def _screen_text(key: str, row: pd.Series, names: Pseudonymizer, config) -> str:
    if key == "closed":
        share = _pct(row["exclusivity"])
        return (
            f"Exclusivity {_f2(row['exclusivity'])}: {share} of these firms' co-bidding is with "
            f"each other. With the same firms bidding the same number of times in "
            f"{config.n_null} reshuffled markets, the average was {_f3(row['null_exclusivity'])} "
            f"(p {_pval(row['p_exclusivity'])}). The threshold for this screen is "
            f"{_f2(config.exclusivity_min)}."
        )
    if key == "rotation":
        if not np.isfinite(row["rotation_p"]):
            return (
                f"Not tested. The test needs at least {config.rotation_min_wins} tenders won by "
                f"members with more than one winner among them. This group has "
                f"{int(row['n_member_wins'])}."
            )
        return (
            f"{int(row['n_wins'])} wins by {int(row['n_winners'])} members changed hands in "
            f"{_f1(row['runs'])} runs. Chance predicts about {_f1(row['expected_runs'])}. "
            f"p {_pval(row['rotation_p'])}, adjusted for the groups tested: "
            f"{_pval(row['rotation_q'])}."
        )
    if key == "cover":
        if not np.isfinite(row["cover_p"]) or row["cover_firm"] is None:
            return (
                f"No member with at least {config.cover_min_bids} bids on decided tenders won a "
                "quarter or less of what equal odds would give."
            )
        firm = names.label("firm", row["cover_firm"])
        return (
            f"{firm} bid on {int(row['cover_bids'])} decided tenders alongside other members and "
            f"won {int(row['cover_wins'])}. Equal odds would give about "
            f"{_f1(row['cover_expected'])}. Adjusted p {_pval(row['cover_q'])}."
        )
    if not np.isfinite(row["median_relative_price"]):
        return (
            f"Not tested. Fewer than {config.price_min_awards} of the group's awards have both "
            "an award value and an estimate."
        )
    if not np.isfinite(row["price_p_value"]):
        return (
            f"Median award {_f3(row['median_relative_price'])} of the estimate over "
            f"{int(row['n_priced_awards'])} awards. No comparable tenders to set it against."
        )
    return (
        f"Median award {_f3(row['median_relative_price'])} of the estimate over "
        f"{int(row['n_priced_awards'])} awards, against {_f3(row['benchmark_median'])} for other "
        f"contested tenders in the same segments. {_pct(row['share_near_estimate'])} of the "
        f"group's awards are at {NEAR_ESTIMATE:.2f} of the estimate or above "
        f"(others: {_pct(row['benchmark_share_near_estimate'])}). "
        f"Adjusted p {_pval(row['price_q'])}."
    )


def _lead_figure(market, row: pd.Series, names: Pseudonymizer):
    members = row["members"]
    bids, tenders = market.bids, market.tenders
    member_bids = bids.loc[bids["firm"].isin(members)]
    per_tender = member_bids.groupby("tender_id")["firm"].size()
    joint_ids = per_tender.index[per_tender >= 2]
    info = tenders.loc[tenders["tender_id"].isin(joint_ids)].sort_values("order")
    total = len(info)
    info = info.head(MAX_TENDERS_SHOWN)
    shown_bids = bids.loc[bids["tender_id"].isin(info["tender_id"])]
    ratio = (info["award_value"] / info["estimate"]).to_numpy(dtype=float)

    other = "other"
    firm_nodes = [
        {"id": f, "label": names.label("firm", f), "member": True}
        for f in sorted(members, key=lambda f: names.label("firm", f))
    ]
    edges, rows, tender_nodes = [], [], []
    n_outsiders = 0
    for (tender_id, when), rel in zip(
        info[["tender_id", "date"]].itertuples(index=False), ratio, strict=True
    ):
        block = shown_bids.loc[shown_bids["tender_id"] == tender_id]
        inside = block.loc[block["firm"].isin(members)]
        outside = block.loc[~block["firm"].isin(members)]
        label = names.label("tender", tender_id)
        for firm, won in zip(inside["firm"], inside["won"], strict=True):
            edges.append((firm, label, bool(won)))
        if len(outside):
            n_outsiders = max(n_outsiders, len(outside))
            edges.append((other, label, bool(outside["won"].any())))
        winners = block.loc[block["won"], "firm"]
        if len(winners) == 0:
            winner = "not published"
        elif winners.isin(members).all():
            winner = ", ".join(sorted(names.labels("firm", winners)))
        else:
            winner = "another bidder"
        month = _month(when)
        tender_nodes.append(
            {
                "id": label,
                "label": month,
                "tip": f"{len(block)} bidders, {len(inside)} from the group",
            }
        )
        rows.append(
            {
                "tender": label,
                "month": month,
                "bidders": int(len(block)),
                "members": int(len(inside)),
                "winner": winner,
                "relative_price": rel if np.isfinite(rel) and 0.2 <= rel <= 2.0 else None,
            }
        )
    if any(firm == other for firm, _, _ in edges):
        firm_nodes.append({"id": other, "label": "Other bidders", "member": False})

    footnote = (
        f"Showing the first {len(info)} of {total} tenders where two or more members bid."
        if total > len(info)
        else f"All {total} tenders where two or more members bid."
    )
    svg = charts.bipartite(
        firm_nodes,
        tender_nodes,
        edges,
        title=f"Who bid on what: lead {row['group_id']}",
        desc=(
            "Bipartite graph. Group members on the left, the tenders they bid on together on "
            "the right. A line is a bid; a heavier line is the winning bid."
        ),
        footnote=footnote,
    )
    # The same picture as plain data, by label only, for the project site.
    position = {node["id"]: i for i, node in enumerate(firm_nodes)}
    tender_position = {node["id"]: i for i, node in enumerate(tender_nodes)}
    graph = {
        "firms": [{"label": node["label"], "member": node["member"]} for node in firm_nodes],
        "tenders": [
            {"label": r["tender"], "month": r["month"], "bidders": r["bidders"]} for r in rows
        ],
        "edges": [[position[f], tender_position[t], bool(won)] for f, t, won in edges],
        "total": int(total),
    }
    return svg, rows, len(info), graph


def _groups_view(result: ScreenResult, figures: dict):
    groups = result.groups
    if groups.empty:
        return "", []
    min_screens = result.config.min_screens
    points = [
        {
            "x": float(g.exclusivity),
            "y": float(max(g.n_joint_tenders, 1)),
            "highlight": g.n_screens >= min_screens,
            "value": f"exclusivity {g.exclusivity:.2f}, {int(g.n_joint_tenders)} joint tenders",
            "label": f"{g.group_id}: {int(g.size)} firms"
            + (f", {int(g.n_screens)} screens fired" if g.n_screens else ""),
        }
        for g in groups.itertuples(index=False)
    ]
    svg = charts.scatter(
        points,
        title="Every co-bidding group: how closed it is and how many tenders it covers",
        desc=(
            "Scatter plot. Horizontal axis: exclusivity from 0 to 1. Vertical axis: tenders on "
            "which two or more members bid, log scale. Leads are picked out."
        ),
        x_label="Exclusivity: share of the group's co-bidding that is with each other",
        y_label="Tenders with two or more members bidding",
        highlight_label="Lead for review",
        context_label="Other group",
        threshold=result.config.exclusivity_min,
        threshold_label="closed-group threshold",
    )
    figures["groups"] = svg
    top = groups.sort_values("exclusivity", ascending=False).head(30)
    rows = [
        {
            "id": g.group_id,
            "size": int(g.size),
            "exclusivity": g.exclusivity,
            "null": g.null_exclusivity,
            "coherence": g.coherence,
            "joint": int(g.n_joint_tenders),
            "closed_share": g.closed_share,
            "screens": ", ".join(SCREEN_LABELS[s] for s in g.screens) or "none",
        }
        for g in top.itertuples(index=False)
    ]
    return svg, rows


def _price_view(result: ScreenResult, figures: dict) -> dict | None:
    market = result.market
    priced = priced_tenders(market.bids, market.tenders)
    ratio = priced["relative_price"]
    ratio = ratio.loc[ratio.between(0.6, 1.3)]
    if len(ratio) < 30:
        return None
    # Bins are centred on whole hundredths, so the bar "at 0.90" holds every
    # award from 0.895 up to 0.905 of the estimate.
    centres = np.round(np.arange(0.60, 1.3001, 0.01), 2)
    edges = np.round(np.append(centres - 0.005, centres[-1] + 0.005), 3)
    counts, _ = np.histogram(ratio.to_numpy(), bins=edges)
    order = np.argsort(counts)[::-1]
    peaks = sorted(int(i) for i in order[:2] if counts[i] / len(ratio) >= 0.05)
    annotations = [
        {
            "x": float(centres[i]),
            "text": f"{counts[i] / len(ratio):.0%} of awards at {centres[i]:.2f} of the estimate",
            "anchor": "end" if n == 0 and len(peaks) > 1 else "start",
        }
        for n, i in enumerate(peaks)
    ]
    svg = charts.histogram(
        edges.tolist(),
        counts.tolist(),
        title="Award value as a share of the buyer's estimate",
        desc=(
            "Histogram of award value divided by the pre-tender estimate, rounded to the "
            "nearest 0.01, from 0.60 to 1.30."
        ),
        x_label="Award value divided by the buyer's estimate",
        y_label="Awards",
        annotations=annotations,
    )
    figures["award-price"] = svg
    table = [
        {"at": float(centres[i]), "count": int(counts[i])}
        for i in range(len(counts))
        if counts[i] > 0
    ]
    return {
        "svg": Markup(svg),
        "table": table,
        "n": int(len(ratio)),
        "median": float(ratio.median()),
        "peaks": [{"at": float(centres[i]), "share": float(counts[i] / len(ratio))} for i in peaks],
    }


def _tender_view(result: ScreenResult, names: Pseudonymizer) -> dict | None:
    """Tender-level price screens, for sources that publish every bid."""
    screens = result.price
    if screens is None or screens.empty:
        return None
    usable = screens.loc[screens["n_bids"] >= 3].dropna(subset=["cv"])
    if usable.empty:
        return None
    flagged = usable.loc[(usable["cv"] < BENCHMARK_CV) & (usable["rd"] > BENCHMARK_RD)]
    dates = result.market.tenders.set_index("tender_id")["date"]
    rows = [
        {
            "tender": names.label("tender", tender_id),
            "month": _month(dates.get(tender_id)),
            "bids": int(row.n_bids),
            "cv": float(row.cv),
            "rd": float(row.rd) if np.isfinite(row.rd) else None,
            "rule": bool(row.cv < BENCHMARK_CV and np.isfinite(row.rd) and row.rd > BENCHMARK_RD),
        }
        for tender_id, row in usable.sort_values("cv").head(20).iterrows()
    ]
    return {
        "n": int(len(usable)),
        "n_flagged": int(len(flagged)),
        "cv_cut": BENCHMARK_CV,
        "rd_cut": BENCHMARK_RD,
        "rows": rows,
    }


def _validation_view(validation: dict[str, pd.DataFrame] | None, figures: dict) -> dict | None:
    if not validation or "price" not in validation or validation["price"].empty:
        return None
    price = validation["price"]
    cases = [c for c in CASE_TITLES if c in set(price["market"])]
    screens = [*PRICE_SCREENS, "composite"]
    labels = {key: s.label for key, s in PRICE_SCREENS.items()} | {
        "composite": "All screens averaged"
    }
    wide = price.pivot(index="screen", columns="market", values="auc")
    heat = [
        {
            "label": labels[key],
            "cells": [
                {"value": float(wide.loc[key, case]), **_tint(float(wide.loc[key, case]))}
                for case in cases
            ],
        }
        for key in screens
        if key in wide.index
    ]
    cv = price.loc[price["screen"] == "cv"].set_index("market").reindex(cases)
    cv = cv.sort_values("auc", ascending=False)
    svg = charts.dot_whisker(
        [
            {
                "label": CASE_TITLES[case],
                "note": f"{int(r.n_collusive):,} cartel tenders of {int(r.n_tenders):,}",
                "value": float(r.auc),
                "low": float(r.auc_low),
                "high": float(r.auc_high),
            }
            for case, r in cv.iterrows()
        ],
        title="How well the variance screen separates cartel tenders, by case",
        desc=(
            "Dot and whisker chart. One row per documented cartel case. The dot is the AUC of "
            "the coefficient of variation screen with a 95% bootstrap interval. 0.5 is a coin toss."
        ),
        x_label="AUC of the coefficient of variation screen",
    )
    figures["validation"] = svg
    lead_rows = _records(validation.get("leads"), cases)
    with_leads = [r for r in lead_rows if r["leads"] > 0]
    beat_base = [
        r for r in with_leads if np.isfinite(r["precision"]) and r["precision"] > r["base_rate"]
    ]
    return {
        "cases": [CASE_TITLES[c] for c in cases],
        "heat": heat,
        "svg": Markup(svg),
        "rule": _records(validation.get("rule"), cases),
        "cobid": _records(validation.get("cobid"), cases),
        "leads": lead_rows,
        "n_lead_cases": len(lead_rows),
        "n_with_leads": len(with_leads),
        "n_beat_base": len(beat_base),
        "n_cases": len(cases),
        "n_cv_works": int((cv["auc"].dropna() >= 0.6).sum()),
    }


def _records(frame: pd.DataFrame | None, cases: list[str]) -> list[dict]:
    if frame is None or frame.empty:
        return []
    frame = frame.loc[frame["market"].isin(cases)].copy()
    frame["case"] = frame["market"].map(CASE_TITLES)
    frame["_order"] = frame["market"].map({c: i for i, c in enumerate(cases)})
    return frame.sort_values("_order").drop(columns="_order").to_dict("records")


def _tint(value: float) -> dict:
    """Cell shading for an AUC: blue above 0.5, red below, grey at 0.5."""
    if not np.isfinite(value):
        return {"side": "none", "strength": 0.0}
    strength = min(abs(value - 0.5) / 0.4, 1.0) * 0.6
    return {"side": "above" if value >= 0.5 else "below", "strength": round(strength, 3)}


# --------------------------------------------------------------------------
# CSV tables
# --------------------------------------------------------------------------


def _write_tables(result: ScreenResult, names: Pseudonymizer, out_dir: Path) -> None:
    groups = result.groups.copy()
    if not groups.empty:
        groups["members"] = groups["members"].map(
            lambda m: " ".join(sorted(names.labels("firm", m)))
        )
        groups["screens"] = groups["screens"].map(" ".join)
        groups["cover_firm"] = groups["cover_firm"].map(
            lambda f: names.label("firm", f) if isinstance(f, str) and f else ""
        )
        groups["top_segment"] = ""
        for column in ("first_date", "last_date"):
            groups[column] = pd.to_datetime(groups[column]).dt.strftime("%Y-%m")
        groups.to_csv(out_dir / "groups.csv", index=False)
        leads = groups.loc[groups["n_screens"] >= result.config.min_screens]
        leads.to_csv(out_dir / "leads.csv", index=False)
    summary = {k: v for k, v in result.summary.items()}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str), "utf-8")


# --------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------


def _num(value) -> str:
    return f"{int(value):,}"


def _pct(value) -> str:
    return "n/a" if value is None or not np.isfinite(value) else f"{value:.0%}"


def _f1(value) -> str:
    return "n/a" if value is None or not np.isfinite(value) else f"{value:.1f}"


def _f2(value) -> str:
    return "n/a" if value is None or not np.isfinite(value) else f"{value:.2f}"


def _f3(value) -> str:
    return "n/a" if value is None or not np.isfinite(value) else f"{value:.3f}"


def _pval(value) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return "below 0.001" if value < 0.001 else f"{value:.3f}"


def _month(value) -> str:
    stamp = pd.to_datetime(value, errors="coerce")
    return "undated" if pd.isna(stamp) else stamp.strftime("%b %Y")


def _period(first, last) -> str:
    a, b = _month(first), _month(last)
    if a == "undated":
        return "undated"
    return a if a == b else f"{a} to {b}"
