"""Export results as one JSON file for the project site.

The file carries the same content as the HTML report, as plain data: firms,
tenders and buyers by label only, dates to the month. The finished text is
put through the same leak check as the report, and nothing is written if a
real identifier is found.

The export is a database derived from the source data. Where the source is
under the Open Database License, so is this file, and it says so.
"""

from __future__ import annotations

import inspect
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from bidscreen import __version__, report
from bidscreen.anonymize import assert_no_leak
from bidscreen.ingest import LABELLED_CASES
from bidscreen.leads import RULE_OUT, SCREEN_LABELS, SCREENS, ScreenResult
from bidscreen.screens.price import PRICE_SCREENS
from bidscreen.screens.pricing import priced_tenders

FILENAME = "site-data.json"


def build_site_data(
    result: ScreenResult,
    key: bytes,
    validation: dict[str, pd.DataFrame] | None = None,
    demo: ScreenResult | None = None,
) -> dict:
    """Everything the site shows, as a plain dictionary."""
    market, summary = result.market, result.summary
    names = report._fit_labels(result, key)
    data = {
        "meta": {
            "generated": date.today().isoformat(),
            "version": __version__,
            "market": market.title or market.name,
            "description": market.description,
            "source": market.source,
            "licence": "Open Database License (ODbL) 1.0",
            "notice": "Leads for review only. Not evidence of wrongdoing.",
        },
        "summary": {
            "tenders": int(summary["tenders"]),
            "with_bidders": int(summary["tenders_with_bidders"]),
            "with_winner": int(summary["tenders_with_winner"]),
            "bidders": int(summary["firms"]),
            "pairs": int(summary.get("cobid_pairs", 0)),
            "links": int(summary.get("significant_links", 0)),
            "groups": int(summary.get("groups", 0)),
            "leads": int(summary.get("leads", 0)),
            "priced": int(summary.get("priced_awards", 0)),
            "screens_fired": summary.get("screens_fired", {}),
        },
        "config": {k: v for k, v in summary["config"].items() if k != "seed"},
        "screens": [
            {"key": key_, "label": SCREEN_LABELS[key_], "rule_out": RULE_OUT[key_]}
            for key_ in SCREENS
        ],
        "groups": _groups(result),
        "price": _price(result),
        "leads": [_lead(result, row, names) for _, row in result.leads.iterrows()],
        "validation": _validation(validation),
        "demo": _demo(demo),
    }
    return _clean(data)


def write_site_data(
    out_dir: Path | str,
    result: ScreenResult,
    key: bytes,
    validation: dict[str, pd.DataFrame] | None = None,
    demo: ScreenResult | None = None,
) -> Path:
    """Write ``site-data.json`` into ``out_dir`` after checking it for names."""
    data = build_site_data(result, key, validation, demo)
    text = json.dumps(data, indent=1, ensure_ascii=False)
    allow = report.fixed_wording(result.market, inspect.getsource(sys.modules[__name__]))
    assert_no_leak(text, report._real_identifiers(result), allow=allow)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / FILENAME
    path.write_text(text + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# Sections
# --------------------------------------------------------------------------


def _groups(result: ScreenResult) -> list[dict]:
    """One point per co-bidding group, for the scatter plot."""
    return [
        {
            "id": g.group_id,
            "size": int(g.size),
            "exclusivity": round(float(g.exclusivity), 4),
            "joint": int(g.n_joint_tenders),
            "closed_share": _number(g.closed_share, 3),
            "screens": list(g.screens),
        }
        for g in result.groups.itertuples(index=False)
    ]


def _price(result: ScreenResult) -> dict | None:
    """Award over estimate, counted at each hundredth from 0.60 to 1.30."""
    ratio = priced_tenders(result.market.bids, result.market.tenders)["relative_price"]
    ratio = ratio.loc[ratio.between(0.6, 1.3)]
    if len(ratio) < 30:
        return None
    centres = np.round(np.arange(0.60, 1.3001, 0.01), 2)
    edges = np.round(np.append(centres - 0.005, centres[-1] + 0.005), 3)
    counts, _ = np.histogram(ratio.to_numpy(), bins=edges)
    return {
        "n": int(len(ratio)),
        "median": round(float(ratio.median()), 3),
        "bins": [{"at": float(c), "count": int(n)} for c, n in zip(centres, counts, strict=True)],
    }


def _lead(result: ScreenResult, row: pd.Series, names) -> dict:
    view = report._lead_view(result, row, names, {})
    return {
        "id": view["id"],
        "members": view["members"],
        "size": view["size"],
        "period": view["period"],
        "joint": view["n_joint"],
        "closed": view["n_closed"],
        "closed_share": _number(view["closed_share"], 3),
        "wins": view["n_wins"],
        "decided": view["n_decided"],
        "segments": view["n_buyers"],
        "exclusivity": round(float(row["exclusivity"]), 4),
        "screens": view["screens"],
        "rule_out": view["rule_out"],
        "graph": view["graph"],
    }


def _validation(validation: dict[str, pd.DataFrame] | None) -> dict | None:
    if not validation or "price" not in validation:
        return None
    price = validation["price"]
    present = set(price["market"])
    cases = [key for key in report.CASE_TITLES if key in present]
    labels = {key: s.label for key, s in PRICE_SCREENS.items()} | {
        "composite": "All seven averaged"
    }
    why = {key: s.why for key, s in PRICE_SCREENS.items()}
    expected = {key: s.expected for key, s in PRICE_SCREENS.items()}
    indexed = price.set_index(["screen", "market"])

    def cell(screen: str, case: str) -> dict:
        r = indexed.loc[(screen, case)]
        return {
            "auc": _number(r["auc"], 3),
            "low": _number(r["auc_low"], 3),
            "high": _number(r["auc_high"], 3),
        }

    scored = price.loc[price["screen"] == "cv"].set_index("market")
    return {
        "cases": [
            {
                "key": case,
                "title": report.CASE_TITLES[case],
                "description": LABELLED_CASES[case].description,
                "identifies_bidders": LABELLED_CASES[case].has_firms,
                "lowest_bid_wins": LABELLED_CASES[case].lowest_bid_wins,
                "tenders": int(scored.loc[case, "n_tenders"]),
                "cartel_tenders": int(scored.loc[case, "n_collusive"]),
            }
            for case in cases
        ],
        "screens": [
            {
                "key": screen,
                "label": labels[screen],
                "expected": expected.get(screen),
                "why": why.get(screen, "the seven screens, each ranked within the market"),
                "cells": {case: cell(screen, case) for case in cases},
            }
            for screen in [*PRICE_SCREENS, "composite"]
            if screen in set(price["screen"])
        ],
        "rule": _table(validation.get("rule"), cases),
        "cobid": _table(validation.get("cobid"), cases),
        "leads": _table(validation.get("leads"), cases),
        "held_out": [
            {"case": row["key"]} | {k: v for k, v in row.items() if k not in ("case", "key")}
            for row in report.held_out_rows(validation, cases)
        ],
    }


def _table(frame: pd.DataFrame | None, cases: list[str]) -> list[dict]:
    if frame is None or frame.empty:
        return []
    frame = frame.loc[frame["market"].isin(cases)]
    return [
        {"case": row["market"], **{k: v for k, v in row.items() if k != "market"}}
        for row in frame.to_dict("records")
    ]


def _demo(demo: ScreenResult | None) -> dict | None:
    """The planted cartel from the synthetic market, for the animated graph."""
    if demo is None or demo.leads.empty:
        return None
    names = report._fit_labels(demo, b"synthetic-demo")
    row = demo.leads.iloc[0]
    view = report._lead_view(demo, row, names, {})
    return {
        "members": view["members"],
        "joint": view["n_joint"],
        "screens": [s["label"] for s in view["screens"] if s["fired"]],
        "graph": view["graph"],
    }


# --------------------------------------------------------------------------
# JSON hygiene
# --------------------------------------------------------------------------


def _number(value, digits: int):
    if value is None:
        return None
    value = float(value)
    return round(value, digits) if np.isfinite(value) else None


def _clean(value):
    """Make a structure safe for JSON: no NaN, no numpy types, no markup."""
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_clean(v) for v in value]
    if isinstance(value, bool | np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, float | np.floating):
        return float(value) if np.isfinite(value) else None
    if value is None or isinstance(value, int | str):
        return value
    return str(value)
