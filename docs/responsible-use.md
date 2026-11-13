# Responsible use

This tool looks for patterns that have been seen in bid rigging. The same patterns have ordinary causes, and in this project's own tests the ordinary causes usually win. Anything it produces is a lead for a person to review.

## What a lead is

A lead says: under a stated test, this group's bidding is unusual, and here are the numbers. It is a reason to open the tender files.

A lead does not say that a firm colluded, that an official helped, or that a rule was broken. Establishing any of that takes documents, interviews and legal powers that no data screen has.

## How often leads are wrong

Run on four documented cartel cases with identified bidders, the group method used for the Assam data did not find the cartels. It produced leads in two cases, and the tenders it flagged were cartel tenders less often than a random pick. See the README for the tables.

So assume a lead is a false alarm until the tender records say otherwise.

## What the tool does to prevent harm

**Names are replaced before anything is written.** Firms, tenders and buyers get labels such as `FIRM-00042`. The label is the rank of a keyed hash (HMAC-SHA256), so:

- nobody can recover a name by hashing a list of candidate names, because they do not have the key;
- the label itself carries no information about the name;
- the same key and data give the same labels, so a lead can be followed from one run to the next.

**The key stays with the analyst.** It is created on first use in `data/private/pseudonym.key`. Git ignores that directory. Whoever holds the key can rebuild the mapping from labels to names.

**A report with a real name in it is not written.** Before saving, the finished page is searched for every real firm name, tender id and buyer name. If one is found, the run stops and nothing is saved.

**Dates are cut to the month** and per-tender prices are rounded.

**The raw data is not redistributed.** It holds the names of firms and of individual contractors.

## What pseudonyms do not do

The source data is public. A person who downloads it and runs this tool gets the same groups, and with their own key can see the names behind them. Pseudonyms stop this repository from publishing names next to a suspicion. They do not make the analysis impossible to repeat.

That is the right boundary. Reviewing public tender records is legitimate. Publishing a list of named firms under the word "fraud", on the strength of a statistical screen, is not.

## If you use this on real data

Do:

- treat every lead as a question, and start with the list of things to rule out;
- go back to the tender documents before forming a view;
- check identity first. Bidders are matched by name, so two people who share a name are merged;
- keep the key and any de-pseudonymised output private;
- hand a lead that survives review to the body with the power to investigate it. In India that is the Competition Commission of India for bid rigging and the vigilance wing of the buyer for misconduct by officials.

Do not:

- publish names from a lead, in a report, a post, a screenshot or a repository;
- describe a lead as a finding, a detection or a case;
- use a count of screens as a probability;
- change thresholds until a particular firm appears.

## Things that look like collusion and are not

| Pattern | Ordinary cause |
|---|---|
| The same few firms always bid together | a small local market, a contractor class or licence that few firms hold |
| Awards at or near the estimate | an estimate set from an out-of-date schedule of rates |
| Many awards at exactly the same ratio to the estimate | a floor below which bids are treated as abnormally low |
| A firm that bids often and never wins | a small or new firm that is not yet competitive, or bids rejected on paperwork |
| Firms taking turns | capacity limits, or a rule that caps awards per bidder across lots |
| Very similar bids | a published rate schedule that everyone prices from |
