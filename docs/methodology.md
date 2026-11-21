# Methodology

This document defines every statistic the tool computes, the null model behind each test, the thresholds, and the places where the implementation departs from the papers it follows.

## 1. The data model

Every source is reduced to two tables.

**Tenders**, one row per tender: an id, the buyer, a market segment, a date, the buyer's estimate, the award value, and a flag where an authority or court labelled the tender as part of a cartel.

**Bids**, one row per firm per tender: the firm, the bid amount where it is published, and whether the bid won.

A loader fills what its source has and leaves the rest missing. Each screen checks for the columns it needs.

## 2. Price screens

These need the amount of every bid on a tender, losing bids included. For sorted bids b1 <= b2 <= ... <= bn:

| Screen | Definition | Expected under collusion | Minimum bids |
|---|---|---|---:|
| Coefficient of variation | sd(b) / mean(b) | low | 2 |
| Spread | (bn - b1) / b1 | low | 2 |
| Gap between two lowest | (b2 - b1) / b1 | high | 2 |
| Relative distance | (b2 - b1) / sd(b2 ... bn) | high | 3 |
| Skewness | sample skewness, bias-corrected | low (negative) | 3 |
| Kurtosis | sample excess kurtosis, bias-corrected | high | 4 |
| Kolmogorov-Smirnov distance | largest gap between the bids and a uniform spread on [b1, bn] | high | 2 |

Standard deviations use n - 1.

The reasoning is the same for all seven. A cartel that has picked its winner needs the other members to bid, so that the tender looks contested. Those cover bids sit close to each other and safely above the winner. The result is a tight cluster of bids with one bid set apart below it.

**The expected direction is a prior, not a rule.** The validation tables in the README show cases where a screen points the other way.

**Agreement with published values.** The six cartel datasets ship with these screens already computed. The values computed here for the coefficient of variation, spread, skewness, kurtosis and Kolmogorov-Smirnov distance agree with the published columns to the four decimals the files carry, on every tender in all six files. `tests/test_published_values.py` checks this whenever the files are present. The relative distance and the gap between the two lowest bids are computed here from the two lowest bids, as defined in Imhof, Karagok and Rutz (2018), and the values in the files differ from that definition.

**Composite.** Each screen is converted to a rank within the market, oriented so that a high rank is what the literature expects under collusion, and the ranks are averaged. Nothing is fitted to the labels.

**Benchmark rule.** A tender meets the rule when its coefficient of variation is below 0.06 and its relative distance is above 1, after Imhof, Karagok and Rutz (2018).

## 3. The bipartite graph and the co-bidding network

Firms are one set of nodes and tenders the other. A bid is an edge. Tenders with a single bidder link nobody to anybody and are left out.

Projecting the graph onto firms gives the co-bidding network. Two firms A and B are linked with weight

    w(A, B) = |T(A) and T(B)| / |T(A) or T(B)|

where T(A) is the set of tenders A bid on. This is the Jaccard overlap of the two tender sets, as in Wachs and Kertesz (2019).

### Is a pair close, or just busy?

Two active firms meet often by chance. For each pair, the tool computes the probability of at least the observed number of joint tenders if the two firms had picked their tenders independently. That is a hypergeometric tail:

    p = P(X >= joint),  X ~ Hypergeometric(N, n_A, n_B)

N is not the whole market. It is the number of tenders in the **segments where both firms have bid**, and n_A and n_B are counted in those segments only. Without that, two firms would look close merely for serving the same buyer.

A pair becomes a **link** when it has at least 3 joint tenders and its p-value survives a Benjamini-Hochberg correction at a false discovery rate of 0.01. The correction is taken over every pair that co-bid at least once. P-values are computed only for pairs with at least 3 joint tenders, and ranks are taken within those, which can only make the correction stricter.

### Segments

A segment is the part of the market within which firms could plausibly have bid for each other's tenders. For the Assam data a segment is a buyer within a postal region, the first three digits of the PIN code on the tender. The cartel case files have no such field and are treated as one segment each.

### Groups

Groups are grown on the links. Starting from one firm, the neighbour that most raises the group's fitness is added, until no neighbour raises it. Fitness is

    f(G) = s_in / (s_in + s_out)

where s_in is the total weight of links inside the group and s_out the total weight of links leaving it. This is the fitness function of Lancichinetti, Fortunato and Kertesz (2009) with its exponent set to 1. Groups may overlap. A group that only stops growing because it reached 25 members has no natural boundary and is discarded. Near-copies (more than half their members shared with a fitter group) are dropped.

### Coherence and exclusivity

Both are measured on the full co-bidding network, not only on the links.

- **Exclusivity** = s_in / (s_in + s_out). The share of the members' co-bidding weight that is with each other.
- **Coherence** = geometric mean of the weights inside the group, divided by their arithmetic mean (Onnela et al. 2005). It is 1 when members co-bid with each other evenly.

### The null model

The market is reshuffled: two bids (firm 1, tender 1) and (firm 2, tender 2) in the same segment swap tenders, as long as that creates no duplicate bid. Every firm keeps its number of bids, every tender keeps its number of bidders, and nobody leaves their segment. Five swaps are attempted per bid. This is the null model of Wachs and Kertesz, with the segment in place of their product category.

Each group's exclusivity is recomputed in 20 reshuffled markets. The p-value is the share of reshuffles in which the group is at least as exclusive as it really is, with the usual +1 correction, so the smallest possible value is 1/21. With fewer than 19 reshuffles the p-value could never reach 0.05 and the screen could never fire, so the tool refuses such a setting instead of running it. The report says when a group's p-value is as small as the number of reshuffles allows.

### Differences from Wachs and Kertesz (2019)

1. **Groups are searched for on significant links, not on the full network.** On a market with thousands of occasional bidders, one-off encounters would otherwise form groups, and the search would not be tractable.
2. **The fitness exponent is 1.** The paper uses 1.5 and an additional size term.
3. **Each group is compared with itself in reshuffled markets.** The paper compares with the 80th percentile of all groups found in reshuffled markets.

### What the null test does and does not do

Real markets are far more structured than any reshuffle. On the Assam data, 326 of 338 groups beat the null. Passing it is a minimum requirement and it does not rank anything. The closed-group screen therefore also requires an exclusivity of at least 0.25, which is a judgement call about effect size.

## 4. Outcome screens

Each is applied to the tenders where at least two members of a group bid.

### Winner rotation

Take the tenders won by a member, in time order, and write down who won each. A run is a stretch of consecutive tenders won by the same firm. If members take turns, the sequence has more runs than a shuffled copy of itself.

The test is the Wald-Wolfowitz runs test for several categories (Mood 1940), with its p-value from 2,000 shuffles of the observed sequence. Shuffling keeps each firm's number of wins, so a firm that simply wins more often does not trigger the screen.

- **Mid-p.** The number of runs is a whole number, and many shuffles tie with the observed value. Counting every tie against the group, as an ordinary permutation p-value does, made the test fire on 0.3% to 3% of random winner sequences at a nominal 5%. The p-value is therefore the mid-p (Lancaster 1961): shuffles with more runs count fully, ties count half. On random sequences of 8 to 40 wins among 2 to 5 firms it now fires 2% to 6% of the time at a nominal 5%.
- **Simultaneous tenders.** Tenders opened at the same moment have no order between them. For each batch of them, the statistic is the number of runs to expect when the batch is put in random order, computed exactly: inside a batch of size b, two neighbours differ with probability 1 minus the share of ordered pairs with equal labels; across the boundary of two batches, the neighbours are a random member of each. Every shuffled sequence is scored the same way, so batches no longer make the test conservative.
- Needs at least 8 wins by members and at least 2 distinct winners. Seven alternating wins between two firms is the least that reaches p < 0.05.

### Persistent losing bidder

For each bid, the chance of winning under equal odds is the number of winners in the tender divided by the number of bidders. Summed over a firm's bids, that is its expected number of wins. The p-value is the probability of winning as few tenders as it did, or fewer, from the exact distribution of a sum of independent trials with unequal probabilities.

A member qualifies only when it has at least 10 bids on decided tenders **and** won at most a quarter of its expected number. The second condition matters. Without it, any firm that is merely less competitive than a strong incumbent is flagged once it has bid often enough, which is what happened on the Ohio data during development.

The equal-odds null is crude: firms differ in cost and quality. The screen is reported only inside a group.

A group's p-value is the smallest among its qualifying members. A group with members to test but none that qualifies gets a p-value of 1, so that it still counts in the multiple-testing correction below.

### Awards near the estimate

Relative price is the award value divided by the buyer's estimate. Ratios outside 0.2 to 2.0 are treated as data errors.

Fewer bidders means less pressure on price, and a group found on the co-bidding network tends to bid where few others do. Compared with all tenders, its awards would sit near the estimate even if every bid were honest, and the screen would repeat what the closed-group screen already says. So each of the group's awards is compared only with tenders from the same segment that drew as many bidders, in bands of 2, 3, 4, 5 to 6, and 7 or more identified bidders. Tenders where two or more members bid are left out of the comparison.

The comparisons are combined across strata with the stratified Wilcoxon test of van Elteren (1960): a rank-sum statistic per stratum, weighted by 1 / (stratum size + 1), with the variance corrected for ties and a one-sided normal p-value. With a single stratum it is the Mann-Whitney test. Awards in a stratum with nothing to compare against are dropped. Needs 5 compared awards and 5 comparison tenders. The benchmark median shown in the report is weighted to the group's mix of strata.

On the Assam data, with award prices shuffled among tenders that share a segment and a bidder band, so that no group effect is left but the link between bidder count and price is kept, a comparison with all contested tenders in the same segments flagged 0 to 7 groups across five shuffles. The stratified test flagged 0 or 1.

The level of the ratio is never read on its own. See the note on price piles in the README.

### Multiple testing

One test per group is run for each outcome screen. P-values are adjusted across the groups that could be tested (Benjamini-Hochberg). A group counts as tested when it had the data the test needs, whatever the result. An earlier version left out groups whose cover test found no qualifying member, which corrected over 14 groups instead of 56 on the Assam data and let too many through and a screen fires at a false discovery rate of 0.10. The cover test picks the most extreme member of a group, so its p-value is first multiplied by the number of members tested.

## 5. Leads

A lead is a group on which at least two of the four screens fired. Leads are listed with the most screens first.

The count of screens orders a reading list. It is not a probability and not a score of guilt. The screens are not independent. A group that is closed has fewer bidders per tender, which pushes awards up for ordinary reasons; the price screen compares tenders with the same number of bidders to keep the two apart, but other shared causes remain.

## 6. Validation

For each documented case, each screen is scored by its AUC: the probability that a randomly chosen cartel tender ranks above a randomly chosen competitive one. Intervals are 95% percentile intervals from 500 bootstrap resamples of tenders.

A tender is counted as a cartel tender when the dataset flags it. For pairs, a pair is positive when both firms are flagged as cartel members. For leads, a tender is flagged when at least two members of a lead group bid on it.

These are descriptive, in-sample checks. No model is trained, so there is no train and test split to leak across, but six cases are six cases.

## 7. Thresholds

All of these are in `ScreenConfig` and most can be set from the command line.

| Setting | Default | Meaning |
|---|---:|---|
| `min_joint` | 3 | joint tenders before two firms can be linked |
| `fdr` | 0.01 | false discovery rate for links |
| `min_group`, `max_group` | 3, 25 | group size limits |
| `n_null` | 20 | reshuffled markets |
| `alpha` | 0.05 | level for the exclusivity test |
| `exclusivity_min` | 0.25 | exclusivity needed for the closed-group screen |
| `outcome_fdr` | 0.10 | false discovery rate for outcome screens |
| `rotation_min_wins` | 8 | wins needed to test rotation |
| `cover_min_bids` | 10 | bids needed to test a member |
| `price_min_awards` | 5 | priced awards needed to test a group |
| `min_screens` | 2 | screens that must fire for a lead |

## 8. Known limits

- **Identity is a name.** Bidders are matched on a normalised name. Namesakes are merged, renamed firms are split, and related firms under different names are not connected. Registration data would fix this and is not public in bulk. Matching drops the M/s prefix and the titles Mr, Mrs and Smt, and keeps Sri, Shri and Dr, which begin many firm names: dropping them merged 148 Assam names with a namesake that lacked the word.
- **Bidder lists may be incomplete.** In the Assam data the number of bidders listed equals the number the portal reports for 44% of tenders.
- **Segments are coarse.** A buyer within a postal region is a rough stand-in for a local market.
- **Group search is greedy.** A different seed order or exponent gives somewhat different groups.
- **No ground truth for Assam.** The rate of false leads there cannot be estimated.
