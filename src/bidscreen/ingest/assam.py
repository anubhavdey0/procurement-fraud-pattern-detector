"""Assam public procurement data, published by CivicDataLab.

Source: https://github.com/CivicDataLab/assam-tenders-data, released under the
Open Database License (ODbL). The file is an Open Contracting (OCDS) style
package scraped from the state's e-procurement portal.

What the file has, per tender:

* who bid (name only) and the status each bid reached;
* who was awarded the contract and for how much;
* the buyer's estimate.

What it does not have is the amount of each losing bid. The price screens in
``bidscreen.screens.price`` therefore cannot run here. Everything computed on
this source rests on who bid with whom, who won, and the award value.

Bidder lists are published for about 10,000 of the 43,000 tenders, almost all
from fiscal years 2021-22 and 2022-23.

Market segments. The null model reshuffles bids within a segment, so the
segment has to capture who could plausibly have bid for what. Here a segment
is a buyer within a postal region (the first three digits of the PIN code on
the tender). Contractors in Assam mostly work near home, and without the
region every cluster of local contractors would look like a closed group.
"""

from __future__ import annotations

import json
import pickle
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from bidscreen.model import Market
from bidscreen.names import normalise_firm_name

SOURCE = (
    "CivicDataLab, Assam Public Procurement Data 2016-2022 "
    "(github.com/CivicDataLab/assam-tenders-data), Open Database License"
)
DEFAULT_PATH = Path("data/raw/assam/ocds_mapped_data.json.zip")
WON_STATUS = "Accepted-AOC"
_CACHE_VERSION = 4  # bump whenever parsing or name matching changes

# The portal writes dates as year-day-month. ISO order is tried as a fallback.
_DATE_FORMATS = ["%Y-%d-%m %H:%M", "%Y-%m-%d %H:%M", "%Y-%d-%m", "%Y-%m-%d"]


def load_assam(path: Path | str = DEFAULT_PATH, cache_dir: Path | str | None = None) -> Market:
    """Load the Assam OCDS package as a :class:`Market`.

    Parsing the package takes most of a minute. With ``cache_dir`` set, the
    parsed tables are kept there and reused until the source file changes.
    The cache holds real names, so it must stay in an ignored directory.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing. Run `bidscreen fetch assam` first.")
    cache = None
    if cache_dir is not None:
        stat = path.stat()
        cache = Path(cache_dir) / f"assam-{stat.st_size}-{int(stat.st_mtime)}-v{_CACHE_VERSION}.pkl"
        if cache.exists():
            with cache.open("rb") as handle:
                return pickle.load(handle)
    market = _parse(path)
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        with cache.open("wb") as handle:
            pickle.dump(market, handle)
    return market


def _parse(path: Path) -> Market:
    releases = _read_releases(path)

    tender_rows: dict[str, dict] = {}
    bid_rows: dict[tuple[str, str], dict] = {}
    winners_added = 0

    for release in releases:
        tender = _first(release.get("tender"))
        if not tender or not tender.get("id"):
            continue
        tender_id = str(tender["id"])
        buyer = (_first(release.get("buyer")) or {}).get("name") or "unknown"
        awards = release.get("awards") or []
        award_values = [(_first(a.get("value")) or {}).get("amount") for a in awards]
        award_values = [v for v in award_values if v is not None]

        region = _region(tender)
        tender_rows[tender_id] = {
            "tender_id": tender_id,
            "segment": f"{buyer} / PIN {region}",
            "buyer": buyer,
            "region": region,
            "date_raw": (_first(tender.get("bidOpening")) or {}).get("date")
            or tender.get("datePublished"),
            "estimate": (_first(tender.get("value")) or {}).get("amount"),
            # A tender split across several awards has no single price to compare.
            "award_value": award_values[0] if len(award_values) == 1 else np.nan,
            "n_awards": len(awards),
            "collusive": None,
            "category": _category(tender),
            "method": tender.get("procurementMethod"),
            "n_bidders_reported": tender.get("numberOfTenderers"),
            "fiscal_year": tender.get("fiscalYear"),
        }

        seen: set[str] = set()
        for block in release.get("bids") or []:
            for detail in block.get("details") or []:
                firm = normalise_firm_name((_first(detail.get("tenderers")) or {}).get("name"))
                if not firm:
                    continue
                seen.add(firm)
                row = bid_rows.setdefault(
                    (tender_id, firm),
                    {"tender_id": tender_id, "firm": firm, "won": False, "status": None},
                )
                status = detail.get("status")
                row["status"] = status or row["status"]
                row["won"] = row["won"] or status == WON_STATUS

        for award in awards:
            firm = normalise_firm_name((_first(award.get("suppliers")) or {}).get("name"))
            if not firm:
                continue
            if firm not in seen:
                # Only add the winner when the tender has a bidder list at all.
                # Otherwise the tender would look like a single-bid tender.
                if not seen:
                    continue
                winners_added += 1
                seen.add(firm)
            row = bid_rows.setdefault(
                (tender_id, firm),
                {"tender_id": tender_id, "firm": firm, "won": False, "status": WON_STATUS},
            )
            row["won"] = True

    tenders = pd.DataFrame(list(tender_rows.values()))
    tenders["date"] = _parse_dates(tenders.pop("date_raw"))
    # Seconds since 1970, as a float so that an unparsed date stays missing.
    tenders["order"] = (tenders["date"] - pd.Timestamp(0)) / pd.Timedelta(seconds=1)
    tenders["estimate"] = pd.to_numeric(tenders["estimate"], errors="coerce")
    tenders.loc[tenders["estimate"] <= 0, "estimate"] = np.nan
    tenders["award_value"] = pd.to_numeric(tenders["award_value"], errors="coerce")
    tenders.loc[tenders["award_value"] <= 0, "award_value"] = np.nan

    bids = pd.DataFrame(list(bid_rows.values()))
    bids["bid_value"] = np.nan
    bids["cartel_member"] = None
    bids["cartel"] = None

    notes = [
        "losing bid amounts are not published, so price screens cannot run",
        "bidders are matched by normalised name; namesakes are merged and renamed firms are split",
    ]
    if winners_added:
        notes.append(
            f"{winners_added} awards named a supplier missing from the bidder list; "
            "the supplier was added as a bidder"
        )

    return Market(
        name="assam",
        title="Assam, India",
        tenders=tenders,
        bids=bids,
        description="India: Assam state tenders, fiscal years 2016-17 to 2022-23.",
        source=SOURCE,
        currency="INR",
        lowest_bid_wins=True,
        notes=notes,
    )


def _read_releases(path: Path) -> list[dict]:
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            members = [
                n for n in archive.namelist() if n.endswith(".json") and not n.startswith("__")
            ]
            if not members:
                raise ValueError(f"{path} holds no JSON file")
            with archive.open(members[0]) as handle:
                package = json.load(handle)
    else:
        with path.open(encoding="utf-8") as handle:
            package = json.load(handle)
    releases = package.get("releases") if isinstance(package, dict) else package
    if not isinstance(releases, list):
        raise ValueError(f"{path} is not an OCDS release package")
    return releases


def _first(value):
    """The package wraps single objects in one-element lists. Unwrap them."""
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _category(tender: dict) -> str | None:
    item = _first(tender.get("items")) or {}
    classification = _first(item.get("classification")) or {}
    return classification.get("description")


def _region(tender: dict) -> str:
    """Postal region: the first three digits of the tender's PIN code."""
    item = _first(tender.get("items")) or {}
    address = _first(item.get("deliveryAddresses")) or {}
    digits = "".join(ch for ch in str(address.get("postalCode") or "") if ch.isdigit())
    return digits[:3] if len(digits) >= 6 else "unknown"


def _parse_dates(raw: pd.Series) -> pd.Series:
    text = raw.astype("string").str.strip()
    parsed = pd.Series(pd.NaT, index=raw.index, dtype="datetime64[ns]")
    for fmt in _DATE_FORMATS:
        todo = parsed.isna() & text.notna()
        if not todo.any():
            break
        parsed.loc[todo] = pd.to_datetime(text[todo], format=fmt, errors="coerce")
    return parsed
