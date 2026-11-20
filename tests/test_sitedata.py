import dataclasses
import json
import math
import re

import pandas as pd
import pytest

from bidscreen import sitedata
from bidscreen.anonymize import Pseudonymizer
from bidscreen.leads import screen_market
from bidscreen.synthetic import make_market


def validation_tables() -> dict[str, pd.DataFrame]:
    """A small stand-in for the files written by `bidscreen validate`."""
    rows = []
    for market in ("brazil", "usa"):
        for screen in ("cv", "spd", "diffp", "rd", "skew", "kurt", "ks", "composite"):
            rows.append(
                {
                    "market": market,
                    "screen": screen,
                    "expected": "low",
                    "n_tenders": 100,
                    "n_collusive": 30,
                    "auc": 0.7,
                    "auc_low": 0.6,
                    "auc_high": float("nan"),
                }
            )
    leads = pd.DataFrame(
        [{"market": "usa", "leads": 3, "n_flagged": 319, "precision": 0.03, "base_rate": 0.13}]
    )
    return {"price": pd.DataFrame(rows), "leads": leads}


def walk(value):
    """Every leaf of a nested structure."""
    if isinstance(value, dict):
        for item in value.values():
            yield from walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk(item)
    else:
        yield value


@pytest.fixture(scope="module")
def realistic():
    """The synthetic market under another name, so its identifiers count as real."""
    market = dataclasses.replace(make_market(seed=0), name="realistic")
    return screen_market(market)


def test_export_has_every_section(realistic, tmp_path):
    path = sitedata.write_site_data(
        tmp_path, realistic, key=b"k", validation=validation_tables(), demo=realistic
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data) == {
        "meta",
        "summary",
        "config",
        "screens",
        "groups",
        "price",
        "leads",
        "validation",
        "demo",
    }
    assert data["summary"]["leads"] == len(data["leads"]) == 1
    assert "seed" not in data["config"]
    assert [s["key"] for s in data["screens"]] == ["closed", "rotation", "cover", "price"]
    assert len(data["price"]["bins"]) == 71
    assert data["validation"]["cases"][0]["key"] == "brazil"
    assert data["validation"]["screens"][0]["cells"]["usa"]["high"] is None  # NaN becomes null


def test_export_is_strict_json(realistic, tmp_path):
    path = sitedata.write_site_data(tmp_path, realistic, key=b"k", validation=validation_tables())
    text = path.read_text(encoding="utf-8")
    assert "NaN" not in text and "Infinity" not in text
    data = json.loads(text)
    for leaf in walk(data):
        assert leaf is None or isinstance(leaf, bool | int | float | str)
        if isinstance(leaf, float):
            assert math.isfinite(leaf)


def test_export_carries_labels_not_names(realistic, tmp_path):
    path = sitedata.write_site_data(tmp_path, realistic, key=b"k", demo=realistic)
    text = path.read_text(encoding="utf-8")
    assert "Cartel firm" not in text and "Buyer A" not in text
    assert not re.search(r"SYN-\d{5}", text)
    lead = json.loads(text)["leads"][0]
    assert all(re.fullmatch(r"FIRM-\d{4}", member) for member in lead["members"])
    assert all(re.fullmatch(r"TENDER-\d{4}", t["label"]) for t in lead["graph"]["tenders"])


def test_lead_graph_indices_are_valid(realistic):
    data = sitedata.build_site_data(realistic, key=b"k")
    graph = data["leads"][0]["graph"]
    assert graph["total"] == 48
    assert len(graph["tenders"]) == 40  # the report shows the first 40
    for firm, tender, won in graph["edges"]:
        assert 0 <= firm < len(graph["firms"])
        assert 0 <= tender < len(graph["tenders"])
        assert isinstance(won, bool)
    # Exactly one winning bid per tender, all by members in a closed cartel.
    winners = [tender for _, tender, won in graph["edges"] if won]
    assert sorted(winners) == list(range(len(graph["tenders"])))


def test_export_is_refused_when_a_name_slips_through(realistic, tmp_path, monkeypatch):
    monkeypatch.setattr(Pseudonymizer, "label", lambda self, kind, value: str(value))
    with pytest.raises(AssertionError, match="nothing was written"):
        sitedata.write_site_data(tmp_path, realistic, key=b"k")
    assert not (tmp_path / sitedata.FILENAME).exists()


def test_export_without_validation_or_demo(result):
    data = sitedata.build_site_data(result, key=b"k")
    assert data["validation"] is None and data["demo"] is None
