import pandas as pd
import pytest

from bidscreen.leads import screen_market
from bidscreen.synthetic import make_market


@pytest.fixture(scope="session")
def market():
    """Synthetic market with one planted cartel and every bid amount."""
    return make_market(seed=0)


@pytest.fixture(scope="session")
def result(market):
    return screen_market(market)


@pytest.fixture()
def tiny_bids():
    """Five tenders, five firms, small enough to check by hand.

    T1: A B C    T2: A B    T3: A B D    T4: C D    T5: E alone
    """
    rows = [
        ("T1", "A", True),
        ("T1", "B", False),
        ("T1", "C", False),
        ("T2", "A", False),
        ("T2", "B", True),
        ("T3", "A", True),
        ("T3", "B", False),
        ("T3", "D", False),
        ("T4", "C", True),
        ("T4", "D", False),
        ("T5", "E", True),
    ]
    return pd.DataFrame(rows, columns=["tender_id", "firm", "won"])
