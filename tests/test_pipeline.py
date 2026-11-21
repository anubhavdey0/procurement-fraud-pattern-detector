import dataclasses
import re

import numpy as np
import pandas as pd
import pytest

from bidscreen import charts, validate
from bidscreen.anonymize import Pseudonymizer
from bidscreen.cli import main
from bidscreen.leads import SCREENS, ScreenConfig, lead_tenders, screen_market
from bidscreen.report import build_report
from bidscreen.synthetic import make_market


def cartel_of(market):
    return frozenset(f for f in market.bids["firm"].unique() if f.startswith("Cartel"))


def test_planted_cartel_is_the_only_lead(market, result):
    assert len(result.leads) == 1
    lead = result.leads.iloc[0]
    assert lead["members"] == cartel_of(market)
    assert lead["screens"] == SCREENS  # all four fired
    assert lead["exclusivity"] == pytest.approx(1.0)
    assert lead["closed_share"] == pytest.approx(1.0)
    assert lead["cover_firm"] == "Cartel firm 4"
    assert result.summary["leads"] == 1


def test_lead_tenders_are_the_cartel_tenders(market, result):
    flagged = set(lead_tenders(result)["tender_id"])
    truth = set(market.tenders.loc[market.tenders["collusive"] == True, "tender_id"])  # noqa: E712
    assert flagged == truth
    scored = validate.lead_validation(result)
    assert scored["precision"] == 1.0 and scored["recall"] == 1.0


def test_pipeline_works_without_bid_amounts():
    market = make_market(with_prices=False, seed=1)
    result = screen_market(market)
    assert not market.has_prices and result.price.empty
    assert list(result.leads["members"]) == [cartel_of(market)]


def test_a_market_with_no_cartel_gives_no_leads():
    market = make_market(cartel_tenders=0, seed=2)
    result = screen_market(market)
    assert len(result.leads) == 0


def test_thresholds_are_respected(market):
    strict = screen_market(market, ScreenConfig(min_screens=5))
    assert len(strict.leads) == 0
    assert len(strict.groups) == 1


def test_markets_without_bidder_identities_skip_group_screens(market):
    bids = market.bids.assign(firm="")
    anonymous = dataclasses.replace(market, bids=bids)
    result = screen_market(anonymous)
    assert result.groups.empty and len(result.leads) == 0
    assert not result.price.empty
    assert "note" in result.summary


def test_price_screens_find_the_cartel_tenders(market):
    table = validate.price_screen_validation(market, n_boot=50)
    auc = table.set_index("screen")["auc"]
    assert auc["cv"] > 0.85 and auc["rd"] > 0.9 and auc["composite"] > 0.95
    low, high = table.set_index("screen").loc["cv", ["auc_low", "auc_high"]]
    assert low <= auc["cv"] <= high


def test_auc_basics():
    label = np.array([True, True, False, False])
    assert validate.auc(np.array([4, 3, 2, 1]), label) == 1.0
    assert validate.auc(np.array([1, 2, 3, 4]), label) == 0.0
    assert validate.auc(np.array([1, 1, 1, 1]), label) == 0.5
    assert validate.auc(np.array([4, np.nan, 2, 1]), label) == 1.0
    assert np.isnan(validate.auc(np.array([1, 2]), np.array([True, True])))


def test_cobid_validation_on_the_planted_cartel(market):
    table = validate.cobid_validation(market).set_index("score")
    assert table.loc["jaccard", "n_cartel_pairs"] == 6
    assert table.loc["jaccard", "auc"] > 0.99


# ---------------------------------------------------------------- report


def real_market(market):
    """The synthetic market under another name, so the report treats its
    identifiers as real and the leak check is active."""
    return dataclasses.replace(market, name="realistic")


def test_report_carries_no_real_identifier(market, tmp_path):
    result = screen_market(real_market(market))
    path = build_report(result, tmp_path, key=b"test key")
    page = path.read_text(encoding="utf-8")
    assert "Cartel firm" not in page
    assert "Buyer A" not in page
    assert not re.search(r"SYN-\d{5}", page)
    assert re.search(r"FIRM-\d{4}", page) and re.search(r"TENDER-\d{4}", page)
    assert "It is not a finding" in page
    for name in ("leads.csv", "groups.csv"):
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert "Cartel firm" not in text and "Buyer A" not in text and "SYN-" not in text


def test_report_is_refused_when_a_name_slips_through(market, tmp_path, monkeypatch):
    result = screen_market(real_market(market))
    monkeypatch.setattr(Pseudonymizer, "label", lambda self, kind, value: str(value))
    with pytest.raises(AssertionError, match="nothing was written"):
        build_report(result, tmp_path, key=b"test key")
    assert not (tmp_path / "report.html").exists()


def test_report_has_no_long_dashes_and_valid_figures(result, tmp_path):
    path = build_report(result, tmp_path, key=b"k")
    page = path.read_text(encoding="utf-8")
    assert "—" not in page and "–" not in page
    figures = sorted(p.name for p in (tmp_path / "figures").glob("*.svg"))
    assert "lead-example-light.svg" in figures and "lead-example-dark.svg" in figures
    for name in figures:
        svg = (tmp_path / "figures" / name).read_text(encoding="utf-8")
        assert svg.startswith("<svg") and "var(--viz" not in svg


def test_report_for_a_market_with_no_leads(tmp_path):
    result = screen_market(make_market(cartel_tenders=0, seed=2))
    page = build_report(result, tmp_path, key=b"k").read_text(encoding="utf-8")
    assert "That is a result, not an error" in page


def test_standalone_chart_resolves_colours():
    svg = charts.dot_whisker(
        [{"label": "Case", "value": 0.8, "low": 0.7, "high": 0.9}], title="t", desc="d"
    )
    assert "var(--viz" in charts.VIZ_CSS
    for theme, colours in charts.THEMES.items():
        out = charts.standalone(svg, theme)
        assert "var(--viz" not in out
        assert colours["surface"] in out and colours["series-1"] in out


def test_cli_demo(tmp_path, capsys):
    assert main(["demo", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "report.html").exists()
    printed = capsys.readouterr().out
    assert "leads for review: 1" in printed


def test_cli_explains_missing_data(tmp_path, capsys):
    assert main(["screen", "assam", "--raw-dir", str(tmp_path)]) == 2
    error = capsys.readouterr().err
    assert "bidscreen fetch assam" in error and "Traceback" not in error
    assert main(["validate", "--raw-dir", str(tmp_path), "--out", str(tmp_path / "v")]) == 2
    assert "bidscreen fetch labelled" in capsys.readouterr().err


def test_cli_refuses_too_few_reshuffles(capsys):
    with pytest.raises(SystemExit) as stop:
        main(["demo", "--null", "10"])
    assert stop.value.code == 2
    assert "at least 19" in capsys.readouterr().err


def test_too_few_reshuffles_are_refused():
    # 1/(n + 1) must reach alpha, or the closed-group screen can never fire.
    with pytest.raises(ValueError, match="at least 19"):
        ScreenConfig(n_null=18)
    ScreenConfig(n_null=19)
    with pytest.raises(ValueError, match="at least 99"):
        ScreenConfig(n_null=50, alpha=0.01)


def test_cover_correction_counts_every_testable_group():
    # Two groups had members with enough bids; only one had a member losing
    # by enough to get a p-value. Both belong in the correction.
    from bidscreen.leads import _flag

    groups = pd.DataFrame(
        {
            "members": [frozenset("AB"), frozenset("CD"), frozenset("EF")],
            "exclusivity": [0.5, 0.5, 0.5],
            "p_exclusivity": [0.5, 0.5, 0.5],
            "rotation_p": [np.nan] * 3,
            "rotation_z": [np.nan] * 3,
            "price_p_value": [np.nan] * 3,
            "cover_p": [0.03, np.nan, np.nan],
            "n_members_tested": [1, 2, 0],
        }
    )
    flagged = _flag(groups, ScreenConfig()).set_index(groups.index)
    q = flagged.sort_values("cover_q")["cover_q"].to_numpy()
    # BH over two groups: 0.03 * 2 / 1 = 0.06; the untestable group stays out.
    assert q[0] == pytest.approx(0.06)
    assert q[1] == pytest.approx(1.0)
    assert np.isnan(q[2])
