"""Check the screens against documented cartel cases.

Each labelled market says which tenders and which firms an authority or court
tied to a cartel. That lets every screen be scored on a simple question: if a
reviewer worked down the list this screen produces, would they reach the
cartel's tenders faster than by picking at random?

The score is the AUC: the probability that a randomly chosen cartel tender
ranks above a randomly chosen competitive one. 0.5 is a coin toss. Below 0.5
means the screen points the wrong way in that market.

The per-case tables are in-sample: they show where a screen has carried
signal. ``leave_one_case_out`` asks the harder question a user faces with a
new market: learn from five cases, then score the sixth, which played no part
in the choice. Six cases are still six cases.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import optimize, stats

from bidscreen import graph
from bidscreen.leads import ScreenResult, lead_tenders
from bidscreen.model import Market
from bidscreen.screens.price import PRICE_SCREENS, oriented, tender_price_screens

COMPOSITE = "composite"
# Benchmark rule used by Imhof, Karagok and Rutz (2018) on Swiss road tenders:
# bids unusually close together, with the winner set clearly apart.
BENCHMARK_CV = 0.06
BENCHMARK_RD = 1.0


def auc(score: np.ndarray, label: np.ndarray) -> float:
    """Area under the ROC curve, from ranks. NaN scores are dropped."""
    score = np.asarray(score, dtype=float)
    label = np.asarray(label, dtype=bool)
    keep = np.isfinite(score)
    score, label = score[keep], label[keep]
    n_pos, n_neg = int(label.sum()), int((~label).sum())
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    ranks = stats.rankdata(score)
    return float((ranks[label].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def bootstrap_auc(
    score: np.ndarray, label: np.ndarray, n_boot: int = 500, seed: int = 0
) -> tuple[float, float, float]:
    """AUC with a 95% percentile bootstrap interval over tenders."""
    score = np.asarray(score, dtype=float)
    label = np.asarray(label, dtype=bool)
    keep = np.isfinite(score)
    score, label = score[keep], label[keep]
    point = auc(score, label)
    if not np.isfinite(point):
        return point, float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(n_boot):
        idx = rng.integers(0, score.size, score.size)
        value = auc(score[idx], label[idx])
        if np.isfinite(value):
            draws.append(value)
    if not draws:
        return point, float("nan"), float("nan")
    low, high = np.percentile(draws, [2.5, 97.5])
    return point, float(low), float(high)


def composite_score(screens: pd.DataFrame) -> pd.Series:
    """A training-free summary of the price screens.

    Each screen is turned into a rank within the market, flipped so that a
    high rank is what the literature expects under collusion, and the ranks
    are averaged. Nothing is fitted to the labels.
    """
    ranked = oriented(screens).rank(pct=True)
    return ranked.mean(axis=1, skipna=True).rename(COMPOSITE)


def price_screen_validation(
    market: Market, min_bids: int = 3, n_boot: int = 500, seed: int = 0
) -> pd.DataFrame:
    """AUC of each price screen for telling cartel tenders from the rest."""
    screens, label = scored_tenders(market, min_bids)
    scores = oriented(screens)
    scores[COMPOSITE] = composite_score(screens)

    rows = []
    for key in [*PRICE_SCREENS, COMPOSITE]:
        point, low, high = bootstrap_auc(scores[key].to_numpy(), label, n_boot, seed)
        usable = np.isfinite(scores[key].to_numpy())
        rows.append(
            {
                "market": market.name,
                "screen": key,
                "expected": PRICE_SCREENS[key].expected if key in PRICE_SCREENS else "high",
                "n_tenders": int(usable.sum()),
                "n_collusive": int(label[usable].sum()),
                "auc": point,
                "auc_low": low,
                "auc_high": high,
            }
        )
    return pd.DataFrame(rows)


def benchmark_rule(market: Market, min_bids: int = 3) -> dict:
    """How the fixed rule "CV below 0.06 and RD above 1" does in a market."""
    screens = tender_price_screens(market.bids)
    screens = screens.loc[screens["n_bids"] >= min_bids].dropna(subset=["cv", "rd"])
    label = market.tenders.set_index("tender_id")["collusive"].reindex(screens.index)
    screens, label = screens.loc[label.notna()], label.dropna().astype(bool)
    flagged = (screens["cv"] < BENCHMARK_CV) & (screens["rd"] > BENCHMARK_RD)
    return _confusion(market.name, flagged.to_numpy(), label.to_numpy())


def cobid_validation(market: Market, min_bids: int = 5) -> pd.DataFrame:
    """Does co-bidding closeness single out pairs of cartel members?

    A pair counts as positive when both firms were named as cartel members.
    Only pairs of firms with at least ``min_bids`` bids each are scored.
    """
    if not (market.has_firms and market.has_firm_labels):
        return pd.DataFrame()
    member = market.bids.groupby("firm")["cartel_member"].max().astype(bool)
    pairs = graph.cobid_pairs(market.bids, market.tenders, min_joint=1)
    pairs = pairs.loc[(pairs["n_a"] >= min_bids) & (pairs["n_b"] >= min_bids)]
    both = (pairs["firm_a"].map(member) & pairs["firm_b"].map(member)).to_numpy()
    scores = {
        "jaccard": pairs["jaccard"].to_numpy(),
        "excess co-bidding": -np.log10(pairs["p_value"].clip(lower=1e-300)).to_numpy(),
        "joint tenders": pairs["n_joint"].to_numpy(dtype=float),
    }
    return pd.DataFrame(
        [
            {
                "market": market.name,
                "score": name,
                "n_pairs": int(len(pairs)),
                "n_cartel_pairs": int(both.sum()),
                "auc": auc(values, both),
            }
            for name, values in scores.items()
        ]
    )


def lead_validation(result: ScreenResult) -> dict:
    """Score the leads the full pipeline produces, tender by tender.

    A tender is flagged when at least two members of a lead group bid on it.
    """
    market = result.market
    label = market.tenders.set_index("tender_id")["collusive"].dropna().astype(bool)
    flagged = label.index.isin(lead_tenders(result)["tender_id"])
    out = _confusion(market.name, flagged, label.to_numpy())
    out["groups"] = int(len(result.groups))
    out["leads"] = int(len(result.leads))
    if market.has_firm_labels and len(result.leads):
        member = market.bids.groupby("firm")["cartel_member"].max().astype(bool)
        in_lead = set().union(*result.leads["members"])
        out["lead_firms"] = len(in_lead)
        out["lead_firm_precision"] = float(np.mean([bool(member.get(f, False)) for f in in_lead]))
        out["firm_base_rate"] = float(member.mean())
    return out


LOCO_METHODS = {
    "composite": "All seven averaged, nothing learned",
    "best_elsewhere": "The screen with the best AUC on the other five cases",
    "learned_weights": "Weights fitted on the other five cases",
}
# Grid searched for the learned rule "CV below c and RD above r".
RULE_CV_GRID = np.round(np.arange(0.01, 0.2001, 0.005), 3)
RULE_RD_GRID = np.round(np.arange(0.0, 3.001, 0.1), 1)
# L2 penalty on the fitted weights, worth about one tender of data. It only
# matters when screens move together, as the variance and the spread do.
RIDGE = 1.0


def scored_tenders(market: Market, min_bids: int = 3) -> tuple[pd.DataFrame, np.ndarray]:
    """Raw price screens and cartel labels for the tenders that can be scored."""
    screens = tender_price_screens(market.bids)
    screens = screens.loc[screens["n_bids"] >= min_bids]
    label = market.tenders.set_index("tender_id")["collusive"].reindex(screens.index)
    known = label.notna()
    return screens.loc[known], label.loc[known].astype(bool).to_numpy()


def rank_features(screens: pd.DataFrame) -> pd.DataFrame:
    """Oriented screens as ranks within the market, from 0 to 1.

    Ranks make the screens comparable across markets whose bids differ in
    scale. A screen that cannot be computed for a tender (kurtosis needs four
    bids) sits at the middle, 0.5, so it pulls neither way.
    """
    return oriented(screens).rank(pct=True).fillna(0.5)[list(PRICE_SCREENS)]


def fit_weights(features: list[pd.DataFrame], labels: list[np.ndarray]) -> np.ndarray:
    """Logistic regression of the cartel label on the ranked screens.

    Each market gets its own intercept, so the very different shares of
    cartel tenders (11% in one case, 82% in another) do not leak into the
    weights, and each market counts as much as an average-sized one however
    many tenders it has. Returns one weight per screen.
    """
    x = np.vstack([f.to_numpy() - 0.5 for f in features])
    y = np.concatenate(labels).astype(float)
    market = np.concatenate([np.full(len(f), i) for i, f in enumerate(features)])
    average = np.mean([len(f) for f in features])
    weight = np.concatenate([np.full(len(f), average / len(f)) for f in features])
    n_screens, n_markets = x.shape[1], len(features)
    dummies = np.eye(n_markets)[market]

    def loss(theta: np.ndarray) -> tuple[float, np.ndarray]:
        beta = theta[:n_screens]
        eta = x @ beta + dummies @ theta[n_screens:]
        # log(1 + e^eta) - y * eta, written to stay finite for large |eta|.
        value = np.sum(weight * (np.logaddexp(0.0, eta) - y * eta)) + RIDGE * beta @ beta
        residual = weight * (1.0 / (1.0 + np.exp(-eta)) - y)
        grad = np.concatenate([x.T @ residual + 2 * RIDGE * beta, dummies.T @ residual])
        return float(value), grad

    start = np.zeros(n_screens + n_markets)
    fit = optimize.minimize(loss, start, jac=True, method="L-BFGS-B")
    return fit.x[:n_screens]


def learn_rule(screens: list[pd.DataFrame], labels: list[np.ndarray]) -> tuple[float, float]:
    """Thresholds for "CV below c and RD above r" chosen on training markets.

    The pair with the highest Youden index (share of cartel tenders flagged
    minus share of competitive tenders flagged), averaged over the markets,
    wins. The index ignores how common cartel tenders are, which differs
    from case to case far more than anything a screen can learn.
    """
    return _best_rule(sum(_youden_grid(s, y) for s, y in zip(screens, labels, strict=True)))


def _youden_grid(screens: pd.DataFrame, label: np.ndarray) -> np.ndarray:
    """Youden index of the rule at every grid point, for one market."""
    keep = screens[["cv", "rd"]].notna().all(axis=1).to_numpy()
    cv, rd, y = screens["cv"].to_numpy()[keep], screens["rd"].to_numpy()[keep], label[keep]
    low = cv[None, :] < RULE_CV_GRID[:, None]
    high = rd[None, :] > RULE_RD_GRID[:, None]
    flagged = low[:, None, :] & high[None, :, :]
    tpr = flagged[:, :, y].mean(axis=2) if y.any() else 0.0
    fpr = flagged[:, :, ~y].mean(axis=2) if (~y).any() else 0.0
    return np.broadcast_to(tpr - fpr, (RULE_CV_GRID.size, RULE_RD_GRID.size))


def _best_rule(total: np.ndarray) -> tuple[float, float]:
    i, j = np.unravel_index(np.argmax(total), total.shape)
    return float(RULE_CV_GRID[i]), float(RULE_RD_GRID[j])


def leave_one_case_out(
    markets: list[Market], min_bids: int = 3, n_boot: int = 500, seed: int = 0
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Learn from all cases but one, score the one left out, for each case.

    Three scores are compared on the held-out case: the training-free
    composite, the single screen that did best on the other cases, and a
    weighted combination fitted on them. The fixed rule is compared with the
    same rule given thresholds tuned on the other cases.

    Returns a table of AUCs and a table of how the tuned rule did.
    """
    data = {m.name: scored_tenders(m, min_bids) for m in markets}
    features = {name: rank_features(screens) for name, (screens, _) in data.items()}
    single = {
        name: {key: auc(features[name][key].to_numpy(), label) for key in PRICE_SCREENS}
        for name, (_, label) in data.items()
    }
    youden = {name: _youden_grid(screens, label) for name, (screens, label) in data.items()}
    scores, rules = [], []
    for held in data:
        train = [name for name in data if name != held]
        screens, label = data[held]
        mean_auc = {key: np.mean([single[name][key] for name in train]) for key in PRICE_SCREENS}
        best = max(mean_auc, key=mean_auc.get)
        weights = fit_weights([features[n] for n in train], [data[n][1] for n in train])
        candidates = {
            "composite": (composite_score(screens).to_numpy(), ""),
            "best_elsewhere": (features[held][best].to_numpy(), best),
            "learned_weights": (
                (features[held].to_numpy() - 0.5) @ weights,
                " ".join(f"{k}={w:+.2f}" for k, w in zip(PRICE_SCREENS, weights, strict=True)),
            ),
        }
        for method, (score, detail) in candidates.items():
            point, low, high = bootstrap_auc(score, label, n_boot, seed)
            scores.append(
                {
                    "market": held,
                    "method": method,
                    "n_tenders": int(label.size),
                    "n_collusive": int(label.sum()),
                    "auc": point,
                    "auc_low": low,
                    "auc_high": high,
                    "detail": detail,
                }
            )

        cv_below, rd_above = _best_rule(sum(youden[name] for name in train))
        keep = screens[["cv", "rd"]].notna().all(axis=1).to_numpy()
        flagged = (screens["cv"].to_numpy() < cv_below) & (screens["rd"].to_numpy() > rd_above)
        row = {"cv_below": cv_below, "rd_above": rd_above}
        rules.append(_confusion(held, flagged[keep], label[keep]) | row)
    return pd.DataFrame(scores), pd.DataFrame(rules)


def _confusion(name: str, flagged: np.ndarray, label: np.ndarray) -> dict:
    flagged = np.asarray(flagged, dtype=bool)
    label = np.asarray(label, dtype=bool)
    hits = int((flagged & label).sum())
    base = float(label.mean()) if label.size else float("nan")
    precision = hits / flagged.sum() if flagged.sum() else float("nan")
    return {
        "market": name,
        "n_tenders": int(label.size),
        "n_collusive": int(label.sum()),
        "base_rate": base,
        "n_flagged": int(flagged.sum()),
        "precision": float(precision),
        "recall": float(hits / label.sum()) if label.sum() else float("nan"),
        "lift": float(precision / base) if base and np.isfinite(precision) else float("nan"),
    }
