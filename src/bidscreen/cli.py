"""Command line for bidscreen.

bidscreen demo        run everything on a synthetic market, no downloads
bidscreen fetch       download the public source files
bidscreen validate    score the screens against six documented cartel cases
bidscreen screen      screen a market and write the leads report
bidscreen export-site write the data file the project site reads
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from bidscreen import __version__
from bidscreen.anonymize import DEFAULT_KEY_PATH, load_or_create_key
from bidscreen.ingest import LABELLED_CASES, load_assam, load_labelled
from bidscreen.ingest.download import fetch
from bidscreen.leads import ScreenConfig, screen_market
from bidscreen.model import Market
from bidscreen.report import build_report
from bidscreen.sitedata import write_site_data
from bidscreen.synthetic import make_market

VALIDATION_FILES = {
    "price": "price_screens.csv",
    "rule": "benchmark_rule.csv",
    "cobid": "cobidding.csv",
    "leads": "leads.csv",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bidscreen",
        description="Collusion screens for public tender data. Output is leads for review.",
    )
    parser.add_argument("--version", action="version", version=f"bidscreen {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    demo = commands.add_parser("demo", help="run on a synthetic market with a planted cartel")
    demo.add_argument("--out", default="out/demo", help="output directory")
    demo.add_argument("--seed", type=int, default=0)
    demo.add_argument(
        "--awards-only",
        action="store_true",
        help="blank the losing bid amounts, as in a source that publishes only awards",
    )

    get = commands.add_parser("fetch", help="download the public source files")
    get.add_argument("source", nargs="?", default="all", choices=["all", "assam", "labelled"])
    get.add_argument("--raw-dir", default="data/raw")

    check = commands.add_parser("validate", help="score the screens on documented cartel cases")
    check.add_argument("--raw-dir", default="data/raw")
    check.add_argument("--out", default="out/validation")
    check.add_argument("--bootstrap", type=int, default=500, help="bootstrap draws per interval")

    screen = commands.add_parser("screen", help="screen a market and write the leads report")
    screen.add_argument("source", choices=["assam", *LABELLED_CASES], help="which market")
    screen.add_argument("--raw-dir", default="data/raw")
    screen.add_argument("--out", default=None, help="output directory (default out/<source>)")
    screen.add_argument("--key", default=str(DEFAULT_KEY_PATH), help="pseudonym key file")
    screen.add_argument(
        "--validation",
        default="out/validation",
        help="directory written by `bidscreen validate`, added to the report when present",
    )
    site = commands.add_parser("export-site", help="write the data file the site reads")
    site.add_argument("--raw-dir", default="data/raw")
    site.add_argument("--out", default="site/src/data", help="output directory")
    site.add_argument("--key", default=str(DEFAULT_KEY_PATH), help="pseudonym key file")
    site.add_argument("--validation", default="docs/validation")
    _add_thresholds(screen)
    _add_thresholds(demo)
    _add_thresholds(site)

    args = parser.parse_args(argv)
    handler = {
        "demo": _demo,
        "fetch": _fetch,
        "validate": _validate,
        "screen": _screen,
        "export-site": _export_site,
    }
    return handler[args.command](args)


def _add_thresholds(parser: argparse.ArgumentParser) -> None:
    defaults = ScreenConfig()
    group = parser.add_argument_group("thresholds")
    group.add_argument("--min-joint", type=int, default=defaults.min_joint)
    group.add_argument("--exclusivity-min", type=float, default=defaults.exclusivity_min)
    group.add_argument(
        "--null",
        type=int,
        default=defaults.n_null,
        dest="n_null",
        help="reshuffled markets for the exclusivity test",
    )
    group.add_argument("--min-screens", type=int, default=defaults.min_screens)


def _config(args) -> ScreenConfig:
    return ScreenConfig(
        min_joint=args.min_joint,
        exclusivity_min=args.exclusivity_min,
        n_null=args.n_null,
        min_screens=args.min_screens,
        seed=getattr(args, "seed", 0),
    )


def _demo(args) -> int:
    market = make_market(with_prices=not args.awards_only, seed=args.seed)
    result = screen_market(market, _config(args))
    # A fixed key is fine here: nothing in a synthetic market is real.
    path = build_report(result, args.out, key=b"synthetic-demo", title="Leads for review: demo")
    _print_summary(market, result)
    print(f"\nReport: {path}")
    return 0


def _fetch(args) -> int:
    fetch(args.source, args.raw_dir)
    return 0


def _validate(args) -> int:
    from bidscreen import validate

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    raw = Path(args.raw_dir) / "labelled"
    price, rule, cobid, leads = [], [], [], []
    for key in LABELLED_CASES:
        market = load_labelled(key, raw)
        print(f"{key}: {len(market.tenders):,} tenders", flush=True)
        price.append(validate.price_screen_validation(market, n_boot=args.bootstrap))
        rule.append(validate.benchmark_rule(market))
        if market.has_firms:
            cobid.append(validate.cobid_validation(market))
            leads.append(validate.lead_validation(screen_market(market)))
    frames = {
        "price": pd.concat(price, ignore_index=True),
        "rule": pd.DataFrame(rule),
        "cobid": pd.concat(cobid, ignore_index=True),
        "leads": pd.DataFrame(leads),
    }
    for name, frame in frames.items():
        frame.to_csv(out / VALIDATION_FILES[name], index=False)

    wide = frames["price"].pivot(index="screen", columns="market", values="auc")
    order = [
        s
        for s in ["cv", "spd", "diffp", "rd", "skew", "kurt", "ks", "composite"]
        if s in wide.index
    ]
    print("\nAUC of each price screen, by case (0.5 is a coin toss):")
    print(wide.loc[order, list(LABELLED_CASES)].round(2).to_string())
    print(f"\nTables written to {out}")
    return 0


def _screen(args) -> int:
    raw = Path(args.raw_dir)
    if args.source == "assam":
        market = load_assam(raw / "assam" / "ocds_mapped_data.json.zip", cache_dir="data/interim")
    else:
        market = load_labelled(args.source, raw / "labelled")
    result = screen_market(market, _config(args))
    out = Path(args.out or f"out/{args.source}")
    key = load_or_create_key(args.key)
    path = build_report(result, out, key=key, validation=_load_validation(args.validation))
    _print_summary(market, result)
    print(f"\nReport: {path}")
    print("Names are replaced by labels. The key is in", args.key, "and is not committed.")
    return 0


def _export_site(args) -> int:
    raw = Path(args.raw_dir) / "assam" / "ocds_mapped_data.json.zip"
    market = load_assam(raw, cache_dir="data/interim")
    result = screen_market(market, _config(args))
    demo = screen_market(make_market(seed=0))
    path = write_site_data(
        args.out,
        result,
        key=load_or_create_key(args.key),
        validation=_load_validation(args.validation),
        demo=demo,
    )
    _print_summary(market, result)
    print(f"\nSite data: {path}")
    return 0


def _load_validation(directory: str) -> dict[str, pd.DataFrame] | None:
    folder = Path(directory)
    found = {
        name: pd.read_csv(folder / filename)
        for name, filename in VALIDATION_FILES.items()
        if (folder / filename).exists()
    }
    return found or None


def _print_summary(market: Market, result) -> None:
    s = result.summary
    print(
        f"{market.name}: {s['tenders']:,} tenders, {s['tenders_with_bidders']:,} with a bidder "
        f"list, {s['firms']:,} bidders"
    )
    if "groups" in s:
        print(
            f"  co-bidding pairs: {s['cobid_pairs']:,}   significant links: "
            f"{s['significant_links']:,}   groups: {s['groups']:,}"
        )
        fired = ", ".join(f"{name} {count}" for name, count in s["screens_fired"].items())
        print(f"  screens fired: {fired}")
        print(f"  leads for review: {s['leads']:,}")
    else:
        print(f"  {s.get('note', 'no group screens were run')}")


if __name__ == "__main__":
    sys.exit(main())
