import pandas as pd
import pytest

from bidscreen.anonymize import Pseudonymizer, assert_no_leak, load_or_create_key
from bidscreen.names import normalise_firm_name

FIRMS = [f"firm number {i}" for i in range(60)]


def test_labels_are_stable_for_one_key():
    first = Pseudonymizer(b"key").fit("firm", FIRMS)
    again = Pseudonymizer(b"key").fit("firm", reversed(FIRMS))
    assert first.labels("firm", FIRMS) == again.labels("firm", FIRMS)


def test_labels_change_with_the_key():
    one = Pseudonymizer(b"key one").fit("firm", FIRMS).labels("firm", FIRMS)
    two = Pseudonymizer(b"key two").fit("firm", FIRMS).labels("firm", FIRMS)
    assert one != two
    assert sorted(one) == sorted(two)  # same label set, different assignment


def test_labels_are_opaque_and_unique():
    names = Pseudonymizer(b"key").fit("firm", FIRMS)
    labels = names.labels("firm", FIRMS)
    assert len(set(labels)) == len(FIRMS)
    assert all(label.startswith("FIRM-") and label[5:].isdigit() for label in labels)
    # Alphabetical order of names must not survive as label order.
    assert labels != sorted(labels)


def test_kinds_do_not_share_labels():
    names = Pseudonymizer(b"key").fit("firm", ["x"]).fit("tender", ["x"]).fit("buyer", ["x"])
    assert names.label("firm", "x") == "FIRM-0001"
    assert names.label("tender", "x") == "TENDER-0001"
    assert names.label("buyer", "x") == "BUYER-0001"


def test_unknown_values_raise_without_echoing_the_value():
    names = Pseudonymizer(b"key").fit("firm", ["known"])
    with pytest.raises(KeyError) as error:
        names.label("firm", "secret name")
    assert "secret name" not in str(error.value)
    with pytest.raises(KeyError):
        names.label("buyer", "anything")
    with pytest.raises(ValueError):
        names.fit("person", ["x"])
    with pytest.raises(ValueError):
        Pseudonymizer(b"")


def test_series_keeps_missing_values_missing():
    names = Pseudonymizer(b"key").fit("firm", ["a", "b"])
    out = names.series("firm", pd.Series(["a", None, "b"]))
    assert out.isna().tolist() == [False, True, False]


def test_key_file_is_created_once(tmp_path, monkeypatch):
    monkeypatch.delenv("BIDSCREEN_KEY", raising=False)
    path = tmp_path / "private" / "pseudonym.key"
    first = load_or_create_key(path)
    assert path.exists() and len(first) == 64
    assert load_or_create_key(path) == first
    monkeypatch.setenv("BIDSCREEN_KEY", "from the environment")
    assert load_or_create_key(path) == b"from the environment"


def test_leak_check_raises_on_a_real_name():
    with pytest.raises(AssertionError):
        assert_no_leak("<td>Northwind Example Enterprise</td>", ["northwind example enterprise"])
    assert_no_leak("<td>FIRM-0042</td>", ["northwind example enterprise"])


def test_leak_check_matches_whole_words():
    # "contractor" is someone's registered name; "contractors" is ordinary text.
    assert_no_leak("few contractors are registered", ["contractor"])
    with pytest.raises(AssertionError):
        assert_no_leak("awarded to contractor again", ["contractor"])


def test_leak_check_allows_the_page_s_own_wording():
    page = "Other bidders also took part"
    with pytest.raises(AssertionError):
        assert_no_leak(page, ["other bidders"])
    assert_no_leak(page, ["other bidders"], allow="legend: Other bidders")


def test_leak_check_skips_very_short_names():
    assert_no_leak("the rk co tender", ["rk co"])


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("M/s. Northwind Example Enterprise", "northwind example enterprise"),
        ("M/S NORTHWIND EXAMPLE  ENTERPRISE.", "northwind example enterprise"),
        ("Ms Northwind Example Enterprise", "northwind example enterprise"),
        ("Quillfeather Infra Private Limited", "quillfeather infra pvt ltd"),
        ("Quillfeather Infra Pvt. Ltd.", "quillfeather infra pvt ltd"),
        ("Mr. Tara Placeholder", "tara placeholder"),
        ("Smt Tara Placeholder", "tara placeholder"),
        ("Shri Tara Placeholder", "shri tara placeholder"),
        ("R & D Construction Company", "r and d construction co"),
        ("  ", ""),
        (None, ""),
        ("nan", ""),
    ],
)
def test_name_normalisation(raw, expected):
    assert normalise_firm_name(raw) == expected


def test_normalisation_does_not_merge_different_firms():
    assert normalise_firm_name("Northwind Example Enterprise") != normalise_firm_name(
        "Northwind Example Enterprises"
    )
    assert normalise_firm_name("Md Placeholder") == "md placeholder"  # "Md" is part of a name
    # "Sri" and "Dr" begin many firm names; dropping them would merge namesakes.
    assert normalise_firm_name("Sri Example Traders") != normalise_firm_name("Example Traders")
    assert normalise_firm_name("Dr Example Labs") != normalise_firm_name("Example Labs")
