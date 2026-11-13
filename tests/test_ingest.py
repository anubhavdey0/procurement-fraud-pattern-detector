import json

import numpy as np
import pandas as pd
import pytest

from bidscreen.ingest import load_assam, load_labelled
from bidscreen.ingest.download import SOURCES, fetch, sha256_of
from bidscreen.model import Market


def release(tender_id, buyer, pin, bidders, winner=None, award=None, estimate=1000.0):
    """One record in the shape of the Assam package: single objects wrapped
    in lists, dates written year-day-month."""
    out = {
        "ocid": f"ocds-x-{tender_id}",
        "buyer": [{"name": buyer}],
        "tender": [
            {
                "id": tender_id,
                "value": [{"amount": estimate, "currency": "INR"}],
                "bidOpening": [{"date": "2023-27-04 14:00"}],
                "procurementMethod": "Open Tender",
                "items": [
                    {
                        "classification": [{"description": "Civil Works"}],
                        "deliveryAddresses": [{"postalCode": pin, "streetAddress": "Somewhere"}],
                    }
                ],
            }
        ],
    }
    if bidders:
        out["bids"] = [
            {
                "details": [
                    {"id": str(i), "status": status, "tenderers": [{"name": name}]}
                    for i, (name, status) in enumerate(bidders)
                ]
            }
        ]
    if winner:
        out["awards"] = [{"suppliers": [{"name": winner}], "value": [{"amount": award}]}]
    return out


@pytest.fixture()
def assam_file(tmp_path):
    package = {
        "releases": [
            release(
                "T1",
                "Roads Department",
                "781003.0",
                [("M/s ABC Traders", "Rejected-AOC"), ("Tara Placeholder", "Accepted-AOC")],
                winner="TARA PLACEHOLDER",
                award=950.0,
            ),
            release(
                "T2",
                "Roads Department",
                "785001",
                [("ABC TRADERS.", "Accepted-Finance"), ("Tara Placeholder", "Accepted-Finance")],
            ),
            release("T3", "Health Mission", "", [], winner="Somebody Else", award=10.0),
            release(
                "T4",
                "Health Mission",
                "781003",
                [("ABC Traders", "Rejected-AOC")],
                winner="New Winner Co",
                award=800.0,
            ),
        ]
    }
    path = tmp_path / "package.json"
    path.write_text(json.dumps(package), encoding="utf-8")
    return path


def test_assam_tables(assam_file):
    market = load_assam(assam_file)
    assert isinstance(market, Market) and market.name == "assam"
    assert not market.has_prices
    tenders = market.tenders.set_index("tender_id")
    assert len(tenders) == 4
    # Dates in the source are year-day-month.
    assert tenders.loc["T1", "date"] == pd.Timestamp("2023-04-27 14:00")
    assert tenders.loc["T1", "segment"] == "Roads Department / PIN 781"
    assert tenders.loc["T2", "region"] == "785"
    assert tenders.loc["T3", "region"] == "unknown"
    assert tenders.loc["T1", "award_value"] == 950.0
    assert np.isnan(tenders.loc["T2", "award_value"])


def test_assam_bidders_are_matched_by_normalised_name(assam_file):
    bids = load_assam(assam_file).bids
    assert set(bids["firm"]) == {"abc traders", "tara placeholder", "new winner co"}
    assert (bids["firm"] == "abc traders").sum() == 3
    t1 = bids.loc[bids["tender_id"] == "T1"].set_index("firm")["won"]
    assert t1["tara placeholder"] and not t1["abc traders"]
    assert not bids.loc[bids["tender_id"] == "T2", "won"].any()


def test_assam_winner_missing_from_the_bidder_list(assam_file):
    market = load_assam(assam_file)
    bids = market.bids
    # T4 lists one bidder but names another as the winner: the winner is added.
    t4 = bids.loc[bids["tender_id"] == "T4"].set_index("firm")["won"]
    assert t4.to_dict() == {"abc traders": False, "new winner co": True}
    assert any("missing from the bidder list" in note for note in market.notes)
    # T3 has no bidder list at all, so the award alone does not create one.
    assert "T3" not in set(bids["tender_id"])


def test_assam_cache_round_trip(assam_file, tmp_path):
    first = load_assam(assam_file, cache_dir=tmp_path / "cache")
    assert len(list((tmp_path / "cache").glob("assam-*.pkl"))) == 1
    second = load_assam(assam_file, cache_dir=tmp_path / "cache")
    pd.testing.assert_frame_equal(first.bids, second.bids)


def test_missing_file_says_what_to_do(tmp_path):
    with pytest.raises(FileNotFoundError, match="bidscreen fetch"):
        load_assam(tmp_path / "nope.zip")
    with pytest.raises(FileNotFoundError, match="bidscreen fetch"):
        load_labelled("japan", tmp_path)
    with pytest.raises(KeyError):
        load_labelled("atlantis", tmp_path)


def test_labelled_loader_drops_company_names(tmp_path):
    raw = pd.DataFrame(
        {
            "Tender": [1, 1, 1, 2, 2, 2],
            "Date": [1050537600] * 3 + [1139875200] * 3,
            "Pre-Tender Estimate (PTE)": [100.0] * 3 + [200.0] * 3,
            "Competitors": [11, 12, 12, 11, 13, 14],
            "Name competitors": ["ALPHA KENSETSU", "BETA DOKEN", "BETA DOKEN"]
            + ["ALPHA KENSETSU", "C", "D"],
            "Winner": [1, 0, 0, 0, 1, 0],
            "Collusive_competitor": [1, 1, 1, 0, 0, 0],
            "Bid_value": [90.0, 95.0, 99.0, 150.0, 140.0, 160.0],
            "Collusive_competitor_original": [1, 1, 1, 0, 0, 0],
        }
    )
    raw.to_excel(tmp_path / "5.Japan.xlsx", index=False)
    market = load_labelled("japan", tmp_path)

    everything = market.bids.astype(str).to_string() + market.tenders.astype(str).to_string()
    assert "KENSETSU" not in everything and "DOKEN" not in everything
    assert set(market.bids["firm"]) == {"11", "12", "13", "14"}
    # Firm 12 appears twice in tender 1 and keeps its lowest bid.
    assert len(market.bids) == 5
    assert market.bids.loc[market.bids["firm"] == "12", "bid_value"].item() == 95.0
    tenders = market.tenders.set_index("tender_id")
    assert tenders["collusive"].to_dict() == {"1": True, "2": False}
    assert tenders.loc["1", "date"] == pd.Timestamp("2003-04-17")
    assert tenders.loc["2", "award_value"] == 140.0
    assert market.has_prices and market.has_firm_labels


def test_market_rejects_inconsistent_tables():
    tenders = pd.DataFrame({"tender_id": ["a"]})
    with pytest.raises(ValueError, match="unknown tenders"):
        Market("m", tenders, pd.DataFrame({"tender_id": ["b"], "firm": ["x"], "won": [True]}))
    twice = pd.DataFrame({"tender_id": ["a", "a"], "firm": ["x", "x"], "won": [True, False]})
    with pytest.raises(ValueError, match="duplicate"):
        Market("m", tenders, twice)
    with pytest.raises(ValueError, match="duplicate tender_id"):
        Market("m", pd.DataFrame({"tender_id": ["a", "a"]}), twice.head(0))


def test_download_is_pinned_and_checked(tmp_path):
    assert all(len(s.sha256) == 64 for s in SOURCES)
    # Every URL names a commit, never a moving branch.
    assert all("/main/" not in s.url and "/HEAD/" not in s.url for s in SOURCES)
    target = tmp_path / "file.bin"
    target.write_bytes(b"abc")
    assert sha256_of(target).startswith("ba7816bf")
    with pytest.raises(ValueError):
        fetch("nowhere", tmp_path)
