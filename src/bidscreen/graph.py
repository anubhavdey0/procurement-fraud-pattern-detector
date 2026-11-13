"""The firm-tender bipartite graph and what is read off it.

Firms are one set of nodes, tenders the other, and a bid is an edge. Projecting
that graph onto firms gives the co-bidding network: two firms are linked when
they bid on the same tender, with a weight equal to the overlap of their
tender sets.

The group screen is built on

    Wachs and Kertesz (2019), "A network approach to cartel detection in
    public auction markets", Scientific Reports 9, 10818.

Their argument: a cartel needs its members to meet each other repeatedly and
needs outsiders to stay away. So a cartel should look like a group of firms
that is cohesive (members co-bid with each other evenly) and exclusive (little
of their bidding involves anyone else). Both are judged against a null model
that reshuffles who bids where while keeping every firm's number of bids and
every tender's number of bidders.

Coherence, exclusivity, the Jaccard link weight and the null model are taken
from the paper. Three steps differ, and the differences are deliberate:

1. Groups are searched for on a backbone of links that are individually
   significant (more joint tenders than independent bidding would give, at a
   controlled false discovery rate). The paper searches the full network.
   The backbone keeps the search tractable on a market with thousands of
   occasional bidders and stops one-off encounters from forming groups.
2. Groups are grown with the LFK fitness function at alpha = 1, which makes
   fitness equal to exclusivity. The paper uses alpha = 1.5 and a size term.
3. Each group's exclusivity is compared with the same group's exclusivity in
   the reshuffled markets. The paper compares with the 80th percentile over
   all groups found in reshuffled markets.

A caution that the Assam run makes concrete: real markets are far more
structured than any reshuffle, so almost every group that survives step 1
also beats the null in step 3. Passing the null is a minimum requirement. It
does not rank groups. Ranking is done on the size of the effect (how exclusive
the group is) and on the outcome screens in ``bidscreen.screens``.
"""

from __future__ import annotations

from collections.abc import Iterable

import networkx as nx
import numpy as np
import pandas as pd
from scipy import sparse, stats

DEFAULT_MIN_JOINT = 3
DEFAULT_FDR = 0.01
DEFAULT_MAX_GROUP = 25
PAIR_COLUMNS = ["firm_a", "firm_b", "n_a", "n_b", "n_joint", "jaccard", "expected", "p_value"]
GROUP_COLUMNS = [
    "members",
    "size",
    "n_links",
    "density",
    "s_in",
    "s_out",
    "coherence",
    "exclusivity",
]


# --------------------------------------------------------------------------
# Bipartite graph
# --------------------------------------------------------------------------


def multi_bidder(bids: pd.DataFrame) -> pd.DataFrame:
    """Bids on tenders with at least two identified bidders.

    A tender with one bidder links nobody to anybody, so it is left out of the
    graph, as in the paper.
    """
    known = bids.loc[bids["firm"] != "", ["tender_id", "firm"]].drop_duplicates()
    counts = known.groupby("tender_id")["firm"].transform("size")
    return known.loc[counts >= 2].reset_index(drop=True)


def bipartite_graph(bids: pd.DataFrame) -> nx.Graph:
    """The firm-tender graph as a networkx object, for inspection and export.

    Nodes are ``("firm", id)`` and ``("tender", id)`` tuples so the two sets
    cannot collide.
    """
    edges = multi_bidder(bids)
    graph = nx.Graph()
    graph.add_nodes_from((("firm", f) for f in edges["firm"].unique()), bipartite=0)
    graph.add_nodes_from((("tender", t) for t in edges["tender_id"].unique()), bipartite=1)
    graph.add_edges_from(
        (("firm", f), ("tender", t)) for f, t in zip(edges["firm"], edges["tender_id"], strict=True)
    )
    return graph


def biadjacency(bids: pd.DataFrame) -> tuple[sparse.csr_matrix, np.ndarray, np.ndarray]:
    """The same graph as a sparse tenders-by-firms 0/1 matrix."""
    edges = multi_bidder(bids)
    tender_codes, tender_ids = pd.factorize(edges["tender_id"], sort=True)
    firm_codes, firm_ids = pd.factorize(edges["firm"], sort=True)
    matrix = sparse.csr_matrix(
        (np.ones(len(edges), dtype=np.int32), (tender_codes, firm_codes)),
        shape=(len(tender_ids), len(firm_ids)),
    )
    return matrix, np.asarray(tender_ids), np.asarray(firm_ids)


# --------------------------------------------------------------------------
# Projection onto firms
# --------------------------------------------------------------------------


def cobid_pairs(
    bids: pd.DataFrame,
    tenders: pd.DataFrame | None = None,
    min_joint: int = 1,
    with_p: bool = True,
) -> pd.DataFrame:
    """Every pair of firms that bid on at least ``min_joint`` tenders together.

    ``jaccard`` is the link weight of the co-bidding network: joint tenders
    divided by tenders either firm bid on.

    ``p_value`` is the chance of at least this many joint tenders if the two
    firms picked their tenders independently (a hypergeometric tail). When
    ``tenders`` carries a ``segment`` column, the pool of tenders they could
    have picked from is limited to segments where both firms have bid, so that
    two firms are not called close merely for working with the same buyer.

    The number of pairs that co-bid at least once, whatever ``min_joint`` is,
    is stored in ``pairs.attrs["n_cobid_pairs"]``. ``significant_links`` uses
    it as the number of tests.
    """
    matrix, tender_ids, firm_ids = biadjacency(bids)
    if matrix.shape[0] == 0:
        return _empty_pairs()

    joint = sparse.triu(matrix.T @ matrix, k=1).tocoo()
    total = int(joint.nnz)
    keep = joint.data >= min_joint
    a, b, n_joint = joint.row[keep], joint.col[keep], joint.data[keep].astype(float)
    if a.size == 0:
        return _empty_pairs(total)
    n_firm = np.asarray(matrix.sum(axis=0)).ravel().astype(float)

    pairs = pd.DataFrame(
        {
            "firm_a": firm_ids[a],
            "firm_b": firm_ids[b],
            "n_a": n_firm[a].astype(int),
            "n_b": n_firm[b].astype(int),
            "n_joint": n_joint.astype(int),
            "jaccard": n_joint / (n_firm[a] + n_firm[b] - n_joint),
        }
    )
    if with_p:
        pool, pool_a, pool_b = _shared_pool(matrix, tender_ids, tenders, a, b, n_firm)
        pairs["expected"] = pool_a * pool_b / pool
        pairs["p_value"] = stats.hypergeom.sf(
            n_joint - 1, pool.astype(int), pool_a.astype(int), pool_b.astype(int)
        )
        pairs = pairs.sort_values(["p_value", "n_joint"], ascending=[True, False])
    else:
        pairs["expected"] = np.nan
        pairs["p_value"] = np.nan
    pairs = pairs.reset_index(drop=True)
    pairs.attrs["n_cobid_pairs"] = total
    return pairs


def _empty_pairs(total: int = 0) -> pd.DataFrame:
    pairs = pd.DataFrame(columns=PAIR_COLUMNS)
    pairs.attrs["n_cobid_pairs"] = total
    return pairs


def _shared_pool(matrix, tender_ids, tenders, a, b, n_firm):
    """Size of the tender pool each pair shares, and each firm's bids in it."""
    total = float(matrix.shape[0])
    if tenders is None or "segment" not in tenders.columns:
        return np.full(a.size, total), n_firm[a], n_firm[b]
    segment = tenders.set_index("tender_id")["segment"].reindex(tender_ids).fillna("unknown")
    codes, uniques = pd.factorize(segment)
    if len(uniques) <= 1:
        return np.full(a.size, total), n_firm[a], n_firm[b]
    indicator = sparse.csr_matrix(
        (np.ones(len(codes), dtype=np.int32), (codes, np.arange(len(codes)))),
        shape=(len(uniques), len(codes)),
    )
    per_segment = np.asarray((indicator @ matrix).todense(), dtype=float)  # segments x firms
    sizes = np.asarray(indicator.sum(axis=1)).ravel().astype(float)

    pool = np.empty(a.size)
    pool_a = np.empty(a.size)
    pool_b = np.empty(a.size)
    step = max(1, 2_000_000 // max(1, len(uniques)))
    for start in range(0, a.size, step):
        sl = slice(start, start + step)
        counts_a = per_segment[:, a[sl]]
        counts_b = per_segment[:, b[sl]]
        both = (counts_a > 0) & (counts_b > 0)
        pool[sl] = sizes @ both
        pool_a[sl] = (counts_a * both).sum(axis=0)
        pool_b[sl] = (counts_b * both).sum(axis=0)
    return pool, pool_a, pool_b


def benjamini_hochberg(p_values: np.ndarray, n_tests: int | None = None) -> np.ndarray:
    """Benjamini-Hochberg adjusted p-values (q-values).

    ``n_tests`` is the size of the whole family when ``p_values`` holds only
    part of it. Ranks are then taken within the part, which can only make the
    adjustment stricter.
    """
    p = np.asarray(p_values, dtype=float)
    if p.size == 0:
        return p
    m = max(int(n_tests or 0), p.size)
    order = np.argsort(p)
    scaled = p[order] * m / np.arange(1, p.size + 1)
    adjusted = np.minimum.accumulate(scaled[::-1])[::-1]
    out = np.empty_like(p)
    out[order] = np.clip(adjusted, 0.0, 1.0)
    return out


def significant_links(
    pairs: pd.DataFrame,
    min_joint: int = DEFAULT_MIN_JOINT,
    fdr: float = DEFAULT_FDR,
    n_tests: int | None = None,
) -> pd.DataFrame:
    """Pairs that bid together at least ``min_joint`` times and significantly
    more often than independent bidding would give.

    The false discovery rate is controlled across every pair that co-bid at
    least once. That count is read from ``pairs.attrs`` (set by
    ``cobid_pairs``) unless ``n_tests`` is given.
    """
    if pairs.empty:
        return pairs.assign(q_value=pd.Series(dtype=float))
    if n_tests is None:
        n_tests = pairs.attrs.get("n_cobid_pairs", len(pairs))
    q_value = benjamini_hochberg(pairs["p_value"].to_numpy(dtype=float), n_tests)
    out = pairs.assign(q_value=q_value)
    return out.loc[(out["n_joint"] >= min_joint) & (out["q_value"] <= fdr)].reset_index(drop=True)


def cobid_network(pairs: pd.DataFrame) -> nx.Graph:
    """Co-bidding network: firms as nodes, Jaccard overlap as link weight."""
    graph = nx.Graph()
    for a, b, weight, n in zip(
        pairs["firm_a"], pairs["firm_b"], pairs["jaccard"], pairs["n_joint"], strict=True
    ):
        graph.add_edge(a, b, weight=float(weight), n_joint=int(n))
    return graph


# --------------------------------------------------------------------------
# Groups
# --------------------------------------------------------------------------


def find_groups(
    graph: nx.Graph,
    alpha: float = 1.0,
    min_size: int = 3,
    max_size: int = DEFAULT_MAX_GROUP,
    max_overlap: float = 0.5,
) -> list[frozenset]:
    """Grow a group around every firm and return the distinct ones.

    Starting from one firm, the neighbour that most raises the group's fitness
    is added, until no neighbour raises it. Fitness is the LFK function
    ``s_in / (s_in + s_out) ** alpha`` (Lancichinetti, Fortunato and Kertesz
    2009), where ``s_in`` is the weight of links inside the group and ``s_out``
    the weight of links leaving it. Groups may overlap.

    A group that stops only because it reached ``max_size`` has no natural
    boundary and is discarded. Groups that share more than ``max_overlap`` of
    their members (Jaccard) with a fitter group are dropped, so near-copies do
    not crowd the results.
    """
    adjacency = {
        node: {nbr: data.get("weight", 1.0) for nbr, data in nbrs.items()}
        for node, nbrs in graph.adjacency()
    }
    strength = {node: sum(nbrs.values()) for node, nbrs in adjacency.items()}

    scored: dict[frozenset, float] = {}
    for seed in adjacency:
        group, fitness, complete = _grow(seed, adjacency, strength, alpha, max_size)
        if complete and len(group) >= min_size:
            scored[group] = max(fitness, scored.get(group, 0.0))

    ranked = sorted(scored, key=lambda g: (-scored[g], -len(g), sorted(map(str, g))))
    kept: list[frozenset] = []
    member_of: dict[object, list[int]] = {}
    for group in ranked:
        rivals = {i for member in group for i in member_of.get(member, ())}
        if any(len(group & kept[i]) / len(group | kept[i]) > max_overlap for i in rivals):
            continue
        for member in group:
            member_of.setdefault(member, []).append(len(kept))
        kept.append(group)
    return kept


def _grow(seed, adjacency, strength, alpha, max_size) -> tuple[frozenset, float, bool]:
    """Returns the group, its fitness, and whether growth stopped by itself."""
    members = {seed}
    s_in, s_out = 0.0, strength[seed]
    links = dict(adjacency[seed])  # outside node -> weight of its links into the group
    fitness = 0.0
    while links:
        best, best_fitness = None, fitness
        for node, weight in links.items():
            new_in = s_in + weight
            new_total = new_in + s_out + strength[node] - 2.0 * weight
            if new_total <= 0:
                continue
            candidate = new_in / new_total**alpha
            if candidate > best_fitness + 1e-12:
                best, best_fitness = node, candidate
        if best is None:
            break
        if len(members) >= max_size:
            return frozenset(members), fitness, False
        weight = links.pop(best)
        s_in += weight
        s_out += strength[best] - 2.0 * weight
        members.add(best)
        fitness = best_fitness
        for node, w in adjacency[best].items():
            if node not in members:
                links[node] = links.get(node, 0.0) + w
    return frozenset(members), fitness, True


def group_metrics(bids: pd.DataFrame, groups: Iterable[frozenset]) -> pd.DataFrame:
    """Coherence and exclusivity of each group, measured on the full
    co-bidding network: every pair that ever bid together, weighted by the
    Jaccard overlap of their tender sets.

    coherence    geometric mean of the weights of links inside the group,
                 divided by their arithmetic mean (Onnela et al. 2005). It is
                 1 when members co-bid with each other evenly and falls
                 towards 0 when a few pairs carry all the weight.
    exclusivity  s_in / (s_in + s_out): the share of the members' total
                 co-bidding weight that is with each other.
    """
    groups = list(groups)
    matrix, _, firm_ids = biadjacency(bids)
    column = {firm: i for i, firm in enumerate(firm_ids)}
    members = sorted({f for g in groups for f in g if f in column}, key=column.get)
    position = {firm: i for i, firm in enumerate(members)}
    strength = np.zeros(len(members))
    inner = sparse.csr_matrix((len(members), len(members)))

    if members:
        cols = np.array([column[f] for f in members])
        n_firm = np.asarray(matrix.sum(axis=0)).ravel().astype(float)
        joint = (matrix[:, cols].T @ matrix).tocoo()  # members x all firms
        row, col, count = joint.row, joint.col, joint.data.astype(float)
        other = cols[row] != col
        row, col, count = row[other], col[other], count[other]
        jaccard = count / (n_firm[cols[row]] + n_firm[col] - count)
        strength = np.bincount(row, weights=jaccard, minlength=len(members))
        slot = np.full(matrix.shape[1], -1)
        slot[cols] = np.arange(len(members))
        inside = slot[col] >= 0
        inner = sparse.csr_matrix(
            (jaccard[inside], (row[inside], slot[col[inside]])),
            shape=(len(members), len(members)),
        )

    rows = []
    for group in groups:
        idx = [position[f] for f in group if f in position]
        size = len(group)
        weights = np.array([])
        if len(idx) >= 2:
            block = inner[idx][:, idx].toarray()
            weights = block[np.triu_indices(len(idx), k=1)]
            weights = weights[weights > 0]
        s_in = float(weights.sum())
        s_out = max(float(strength[idx].sum()) - 2.0 * s_in, 0.0) if idx else 0.0
        if weights.size and s_in > 0:
            coherence = float(np.exp(np.log(weights).mean()) / weights.mean())
            exclusivity = s_in / (s_in + s_out)
        else:
            coherence, exclusivity = np.nan, 0.0
        rows.append(
            {
                "members": group,
                "size": size,
                "n_links": int(weights.size),
                "density": weights.size / (size * (size - 1) / 2) if size > 1 else np.nan,
                "s_in": s_in,
                "s_out": s_out,
                "coherence": coherence,
                "exclusivity": exclusivity,
            }
        )
    return pd.DataFrame(rows, columns=GROUP_COLUMNS)


# --------------------------------------------------------------------------
# Null model
# --------------------------------------------------------------------------


def shuffle_bids(
    bids: pd.DataFrame,
    tenders: pd.DataFrame | None,
    rng: np.random.Generator,
    swaps_per_bid: int = 5,
) -> pd.DataFrame:
    """Reshuffle who bids where, within each segment.

    Every firm keeps its number of bids and every tender keeps its number of
    bidders. Two bids (f1, t1) and (f2, t2) swap tenders when that creates no
    duplicate bid. This is the null model of Wachs and Kertesz, with the
    segment playing the role of their product category.
    """
    edges = multi_bidder(bids)
    if tenders is not None and "segment" in tenders.columns:
        segment = edges["tender_id"].map(tenders.set_index("tender_id")["segment"])
        segment = segment.fillna("unknown")
    else:
        segment = pd.Series("all", index=edges.index)

    out_firm: list = []
    out_tender: list = []
    for _, block in edges.groupby(segment.to_numpy(), sort=True):
        firms = block["firm"].tolist()
        tender_ids = block["tender_id"].tolist()
        count = len(firms)
        if count >= 2:
            present = set(zip(firms, tender_ids, strict=True))
            draws = rng.integers(0, count, size=(swaps_per_bid * count, 2))
            for i, j in draws.tolist():
                f1, t1, f2, t2 = firms[i], tender_ids[i], firms[j], tender_ids[j]
                if f1 == f2 or t1 == t2 or (f1, t2) in present or (f2, t1) in present:
                    continue
                present.discard((f1, t1))
                present.discard((f2, t2))
                present.add((f1, t2))
                present.add((f2, t1))
                tender_ids[i], tender_ids[j] = t2, t1
        out_firm.extend(firms)
        out_tender.extend(tender_ids)
    return pd.DataFrame({"tender_id": out_tender, "firm": out_firm})


def exclusivity_null(
    bids: pd.DataFrame,
    tenders: pd.DataFrame | None,
    groups: list[frozenset],
    n_replicates: int = 50,
    seed: int = 0,
) -> np.ndarray:
    """Exclusivity of each group in ``n_replicates`` reshuffled markets.

    Returns an array of shape (groups, replicates). Comparing a group's real
    exclusivity with its row answers: given how much these firms bid and in
    which segments, how often would they end up this closed off by chance?
    """
    rng = np.random.default_rng(seed)
    out = np.zeros((len(groups), n_replicates))
    if not groups:
        return out
    for replicate in range(n_replicates):
        shuffled = shuffle_bids(bids, tenders, rng)
        out[:, replicate] = group_metrics(shuffled, groups)["exclusivity"].to_numpy()
    return out


def exclusivity_p_values(real: np.ndarray, null: np.ndarray) -> np.ndarray:
    """Share of reshuffled markets in which a group is at least as exclusive
    as it really is, with the usual +1 correction."""
    real = np.asarray(real, dtype=float)
    if null.shape[1] == 0:
        return np.full(real.shape, np.nan)
    at_least = (null >= real[:, None] - 1e-12).sum(axis=1)
    return (1.0 + at_least) / (null.shape[1] + 1.0)
