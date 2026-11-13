import networkx as nx
import numpy as np
import pandas as pd
import pytest
from scipy import stats

from bidscreen import graph


def pair(pairs, a, b):
    hit = pairs.loc[
        ((pairs["firm_a"] == a) & (pairs["firm_b"] == b))
        | ((pairs["firm_a"] == b) & (pairs["firm_b"] == a))
    ]
    assert len(hit) == 1
    return hit.iloc[0]


def test_single_bidder_tenders_are_left_out(tiny_bids):
    edges = graph.multi_bidder(tiny_bids)
    assert "T5" not in set(edges["tender_id"])
    assert "E" not in set(edges["firm"])


def test_bipartite_graph_and_matrix_agree(tiny_bids):
    net = graph.bipartite_graph(tiny_bids)
    matrix, tender_ids, firm_ids = graph.biadjacency(tiny_bids)
    assert nx.is_bipartite(net)
    assert net.number_of_edges() == matrix.sum() == 10
    assert list(tender_ids) == ["T1", "T2", "T3", "T4"]
    assert list(firm_ids) == ["A", "B", "C", "D"]
    for i, tender in enumerate(tender_ids):
        for j, firm in enumerate(firm_ids):
            assert bool(matrix[i, j]) == net.has_edge(("firm", firm), ("tender", tender))


def test_jaccard_by_hand(tiny_bids):
    pairs = graph.cobid_pairs(tiny_bids)
    assert len(pairs) == 6 and pairs.attrs["n_cobid_pairs"] == 6
    assert pair(pairs, "A", "B")["n_joint"] == 3
    assert pair(pairs, "A", "B")["jaccard"] == pytest.approx(1.0)
    assert pair(pairs, "A", "C")["jaccard"] == pytest.approx(0.25)
    assert pair(pairs, "C", "D")["jaccard"] == pytest.approx(1 / 3)


def test_jaccard_matches_networkx_projection(market):
    bids = market.bids.head(600)
    net = graph.bipartite_graph(bids)
    firms = [n for n, d in net.nodes(data=True) if d["bipartite"] == 0]
    projected = nx.bipartite.overlap_weighted_projected_graph(net, firms, jaccard=True)
    pairs = graph.cobid_pairs(bids, with_p=False)
    assert len(pairs) == projected.number_of_edges()
    for row in pairs.itertuples(index=False):
        weight = projected[("firm", row.firm_a)][("firm", row.firm_b)]["weight"]
        assert row.jaccard == pytest.approx(weight)


def test_p_value_is_the_hypergeometric_tail(tiny_bids):
    pairs = graph.cobid_pairs(tiny_bids)
    # A and B each bid on 3 of the 4 contested tenders and met on all 3.
    assert pair(pairs, "A", "B")["p_value"] == pytest.approx(0.25)
    assert pair(pairs, "A", "B")["expected"] == pytest.approx(9 / 4)
    assert pair(pairs, "A", "C")["p_value"] == pytest.approx(stats.hypergeom.sf(0, 4, 3, 2))


def test_segments_shrink_the_pool():
    # X and Y always meet, but only because buyer P has no other bidders.
    rows = [(f"P{i}", f, "P") for i in range(5) for f in ("X", "Y")]
    rows += [(f"Q{i}", f, "Q") for i in range(40) for f in ("M", "N", "O")[: 2 + i % 2]]
    frame = pd.DataFrame(rows, columns=["tender_id", "firm", "segment"])
    tenders = frame[["tender_id", "segment"]].drop_duplicates()
    pooled = pair(graph.cobid_pairs(frame), "X", "Y")["p_value"]
    by_segment = pair(graph.cobid_pairs(frame, tenders), "X", "Y")["p_value"]
    assert pooled < 1e-5
    assert by_segment == pytest.approx(1.0)


def test_min_joint_filters_but_keeps_the_test_count(tiny_bids):
    pairs = graph.cobid_pairs(tiny_bids, min_joint=3)
    assert len(pairs) == 1
    assert pairs.attrs["n_cobid_pairs"] == 6


def test_benjamini_hochberg():
    p = np.array([0.01, 0.04, 0.03, 0.20])
    assert graph.benjamini_hochberg(p) == pytest.approx([0.04, 0.04 * 4 / 3, 0.04 * 4 / 3, 0.20])
    # A larger family makes every adjusted value larger.
    assert (graph.benjamini_hochberg(p, n_tests=40) >= graph.benjamini_hochberg(p)).all()
    assert graph.benjamini_hochberg(np.array([])).size == 0


def test_group_metrics_by_hand(tiny_bids):
    metrics = graph.group_metrics(tiny_bids, [frozenset("AB"), frozenset("ABC")])
    ab, abc = metrics.iloc[0], metrics.iloc[1]
    assert ab["s_in"] == pytest.approx(1.0)
    assert ab["exclusivity"] == pytest.approx(0.5)
    assert ab["coherence"] == pytest.approx(1.0)
    assert abc["exclusivity"] == pytest.approx(1.5 / (1.5 + 5 / 6))
    assert abc["coherence"] == pytest.approx(0.0625 ** (1 / 3) / 0.5)
    assert abc["n_links"] == 3 and abc["density"] == pytest.approx(1.0)


def test_unknown_firms_score_zero(tiny_bids):
    metrics = graph.group_metrics(tiny_bids, [frozenset({"nobody", "no one"})])
    assert metrics.loc[0, "exclusivity"] == 0.0
    assert np.isnan(metrics.loc[0, "coherence"])


def test_find_groups_recovers_a_clique():
    net = nx.Graph()
    clique = ["c1", "c2", "c3", "c4"]
    for i, a in enumerate(clique):
        for b in clique[i + 1 :]:
            net.add_edge(a, b, weight=0.9)
    chain = [f"x{i}" for i in range(8)]
    for a, b in zip(chain, chain[1:], strict=False):
        net.add_edge(a, b, weight=0.2)
    net.add_edge("c1", "x0", weight=0.05)
    groups = graph.find_groups(net)
    assert frozenset(clique) in groups


def test_shuffle_keeps_every_count(market):
    rng = np.random.default_rng(3)
    before = graph.multi_bidder(market.bids)
    after = graph.shuffle_bids(market.bids, market.tenders, rng)
    assert len(after) == len(before)
    assert not after.duplicated(["tender_id", "firm"]).any()
    pd.testing.assert_series_equal(
        before.groupby("firm").size().sort_index(), after.groupby("firm").size().sort_index()
    )
    pd.testing.assert_series_equal(
        before.groupby("tender_id").size().sort_index(),
        after.groupby("tender_id").size().sort_index(),
    )
    # Firms stay inside their own segment.
    segment = market.tenders.set_index("tender_id")["segment"]
    home = before.assign(s=before["tender_id"].map(segment)).groupby("firm")["s"].agg(set)
    moved = after.assign(s=after["tender_id"].map(segment)).groupby("firm")["s"].agg(set)
    assert (home == moved).all()
    # And the shuffle did change who bids where.
    merged = before.merge(after, on=["tender_id", "firm"])
    assert len(merged) < len(before)


def test_exclusivity_null_and_p_values(market):
    cartel = frozenset(f for f in market.bids["firm"].unique() if f.startswith("Cartel"))
    real = graph.group_metrics(market.bids, [cartel])["exclusivity"].to_numpy()
    null = graph.exclusivity_null(market.bids, market.tenders, [cartel], n_replicates=19, seed=0)
    assert null.shape == (1, 19)
    assert real[0] == pytest.approx(1.0)
    assert null.max() < 0.5
    assert graph.exclusivity_p_values(real, null)[0] == pytest.approx(1 / 20)
