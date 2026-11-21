# Procurement fraud pattern detector

Collusion screens for public tender data. The output is a list of **leads for a person to review**. It never says that fraud was detected, and it never names a company.

**Project site:** [anubhavdey0.github.io/procurement-fraud-pattern-detector](https://anubhavdey0.github.io/procurement-fraud-pattern-detector/), an interactive tour of the method, the evidence and the Assam leads.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/figures/demo-lead-dark.svg">
  <img src="docs/figures/demo-lead-light.svg" alt="Bipartite graph of one lead in the synthetic demo market. Four firms on the left, forty tenders on the right. Three firms take turns winning and the fourth bids on most tenders without ever winning." width="820">
</picture>

*One lead from the built-in demo market, where a cartel is planted on purpose. Three firms take turns winning and the fourth only ever files losing bids. Every name is replaced by a label.*

## What this project does

1. Builds the **firm-tender bipartite graph** from public tender data: a bid is a link between a firm and a tender.
2. Applies **screens from the bid-rigging literature** (variance, relative distance, co-bidding groups, bid rotation, cover bidding) and does not invent detectors of its own.
3. **Checks every screen against six documented cartel cases** and reports where each one works and where it fails.
4. Applies the screens that the data supports to about 10,000 tenders from **Assam, India**, and writes an anonymised report.

The package is called `bidscreen`. The repository keeps its working title.

**Why not ask an AI chatbot instead?** A chatbot writes text that reads like an analysis. This tool computes one over every bid, has its record measured against proven cartels, gives the same answer every time, and keeps names on your machine. [The full answer](#why-not-just-ask-an-ai-chatbot).

## What came out of it

Three findings, in order of how much weight they can bear.

**1. Price screens work, where every bid amount is published.** On tenders from six documented cartels, the variance screen ranks cartel tenders above competitive ones in four cases and fails in two. No screen works everywhere.

**2. Who bids with whom does not, on its own, find cartels.** A co-bidding network singled out the cartel pairs in one case of four. Leads built only from participation and outcomes found none of the documented cartels.

**3. Indian open tender data supports only the weaker kind of screen.** The Assam data lists bidders and awards but not losing bid amounts. The screen there produces 4 leads from 338 co-bidding groups. Given finding 2, they are a reading list and nothing more.

That third point is the most useful result here: the best-tested screens cannot run on this data, because the amounts of the losing bids are not in it.

## Quick start

No download is needed for the demo. It runs every screen on a synthetic market with a planted cartel and writes a report.

```bash
git clone https://github.com/anubhavdey0/procurement-fraud-pattern-detector.git
cd procurement-fraud-pattern-detector
python -m venv .venv
.venv\Scripts\activate          # Windows. On macOS or Linux: source .venv/bin/activate
pip install -e ".[dev]"

bidscreen demo                  # writes out/demo/report.html
pytest                          # 112 tests, about two minutes (6 need the downloaded data)
```

To reproduce the real results:

```bash
bidscreen fetch                 # downloads the public files (about 30 MB), checks their SHA-256
bidscreen validate              # scores every screen on the six cartel cases (about 5 minutes)
bidscreen screen assam          # screens the Assam tenders, writes out/assam/report.html
```

Python 3.10 or later. The sample report from the Assam run is in [docs/sample/assam-report.html](docs/sample/assam-report.html), and the [project site](https://anubhavdey0.github.io/procurement-fraud-pattern-detector/report/assam.html) serves it directly.

## How it works

```
public tender data
      |
      v
two tables: tenders, bids          one loader per source
      |
      v
firm-tender bipartite graph
      |
      v
co-bidding links                   pairs that bid together more than chance allows
      |
      v
groups of firms                    grown on those links
      |
      v
four screens per group             closed group, rotation, cover bidding, award price
      |
      v
leads for review                   groups where two or more screens fired
      |
      v
anonymised report                  labels for names, refused if a real name slips through
```

Where every bid amount is published, seven price screens also run on each tender.

| Screen | Asks | Needs | Source |
|---|---|---|---|
| Coefficient of variation, spread | Are the bids packed unusually close together? | every bid amount | Abrantes-Metz et al. (2006) |
| Relative distance, gap between two lowest | Is the lowest bid set apart from the rest? | every bid amount | Imhof, Karagok and Rutz (2018) |
| Skewness, kurtosis, Kolmogorov-Smirnov | Is the shape of the bid distribution lopsided or bunched? | every bid amount | Huber and Imhof (2019) |
| Closed group | Is a group's bidding mostly with itself, beyond what reshuffled markets give? | who bid on what | Wachs and Kertesz (2019) |
| Winner rotation | Do members take turns winning more often than chance? | winners, in time order | runs test (Mood 1940) with mid-p (Lancaster 1961); pattern from the OECD guidelines (2009) |
| Persistent losing bidder | Does a member keep bidding and keep losing? | winners | OECD guidelines (2009); Toth et al. (2014) |
| Awards near the estimate | Are the group's awards closer to the estimate than tenders from the same buyers that drew as many bidders? | award value and estimate | Wachs and Kertesz (2019); stratified test of van Elteren (1960) |

Formulas, null models and thresholds are in [docs/methodology.md](docs/methodology.md). Where the implementation differs from a paper, the difference is listed there.

## Checked against documented cartels

The ground truth is six sets of tenders in which a competition authority or a court identified a cartel, assembled by Garcia Rodriguez et al. (2022). Each has every bid, with the cartel's tenders flagged.

The number is the AUC: the chance that a randomly chosen cartel tender ranks above a randomly chosen competitive one. **0.5 is a coin toss. Below 0.5 the screen points the wrong way.**

| Screen | Brazil: Petrobras | Switzerland: Ticino | Japan: Okinawa | Italy: Turin | Switzerland: Graubunden, See-Gaster | USA: Ohio school milk |
|---|---:|---:|---:|---:|---:|---:|
| Coefficient of variation | **0.90** | **0.82** | **0.74** | 0.63 | 0.53 | 0.46 |
| Spread | **0.90** | **0.79** | **0.72** | 0.68 | 0.49 | 0.45 |
| Relative distance | **0.76** | 0.68 | 0.62 | 0.52 | 0.42 | 0.50 |
| Skewness | **0.72** | **0.82** | 0.59 | 0.58 | 0.46 | 0.51 |
| Kurtosis | 0.49 | 0.69 | 0.56 | 0.40 | 0.47 | 0.45 |
| Kolmogorov-Smirnov distance | 0.58 | **0.71** | 0.51 | 0.46 | 0.41 | 0.45 |
| Gap between two lowest bids | 0.38 | 0.55 | 0.43 | 0.48 | 0.43 | 0.53 |
| All seven averaged | **0.80** | **0.86** | 0.66 | 0.57 | 0.43 | 0.46 |
| Cartel tenders / tenders scored | 32 / 100 | 181 / 220 | 123 / 1,080 | 143 / 278 | 2,947 / 3,812 | 272 / 917 |

Bold marks 0.70 or more. Tenders need three or more bids to be scored.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/figures/validation-dark.svg">
  <img src="docs/figures/validation-light.svg" alt="Dot and whisker chart of the AUC of the variance screen in six cartel cases with 95 percent intervals: Petrobras 0.90, Ticino 0.82, Okinawa 0.74, Turin 0.63, Graubunden and See-Gaster 0.53, Ohio school milk 0.46." width="820">
</picture>

What the table says:

- **The variance screen is the workhorse.** Cover bids sit close together, so bids on a rigged tender vary less. It reaches 0.74 to 0.90 in three cases.
- **Two cases defeat every screen.** In the Graubunden and See-Gaster set, cartel members bid alongside outsiders in about 40% of tenders, and an outsider's bid breaks the tight pattern. In the Ohio set most tenders have two bidders, so there is almost no distribution to measure.
- **Averaging the screens does not beat the best one.** The weak screens dilute the strong ones.
- **A fixed rule does not transfer.** "Variance below 0.06 and relative distance above 1", the benchmark of Imhof, Karagok and Rutz, is right 98% of the time on Ticino and 82% on Petrobras, and no better than a random pick on three other cases.

### Learned on five cases, tested on the sixth

The table above was read with all six cases in view, so it flatters whichever screen happens to look best. To check that, each case was set aside in turn and everything was learned from the other five: which screen to trust, weights for all seven screens (a logistic regression, after Huber and Imhof 2019), and new thresholds for the rule. The case set aside played no part in any of it.

| Case set aside | Screen the other five pick | Its AUC | Fitted weights | All seven averaged | Lift, tuned rule | Lift, published rule |
|---|---|---:|---:|---:|---:|---:|
| Brazil: Petrobras | Coefficient of variation | **0.90** | 0.84 | 0.80 | 1.88 | 2.57 |
| Switzerland: Ticino | Coefficient of variation | **0.82** | 0.77 | 0.86 | 1.13 | 1.19 |
| Japan: Okinawa | Coefficient of variation | **0.74** | 0.74 | 0.66 | 1.15 | 1.48 |
| Italy: Turin | Coefficient of variation | 0.63 | 0.61 | 0.57 | 1.00 | 0.97 |
| Switzerland: Graubunden, See-Gaster | Coefficient of variation | 0.53 | 0.49 | 0.43 | 1.01 | 0.94 |
| USA: Ohio school milk | Coefficient of variation | 0.46 | 0.46 | 0.46 | 0.99 | 0.95 |

Lift is the share of flagged tenders that are cartel tenders, divided by the share among all tenders scored. 1 is a random pick.

- **The choice of screen holds up.** Whichever case is set aside, the other five pick the coefficient of variation. Its record in the first table is not the product of picking the winner after the fact.
- **Fitting weights does not help.** The fitted combination is below the variance screen alone in four cases and level with it in two. Beyond the variance screen, the weights change sign from one set of five cases to the next: relative distance gets +0.61 in one fold and -1.78 in another. Whatever a model learns from some cartels about the finer shape of the bids does not carry to the next one.
- **Tuned thresholds do worse than the published ones.** Tuned on five cases, the rule loosens to "variance below about 0.09 and relative distance above 0.2" and flags far more tenders: 80% of those in Okinawa. Its lift is lower than the published rule's in all three cases where that rule works. In the other three, both sit at about 1.

### The network screens, checked the same way

In the four cases that identify bidders, does bidding together single out pairs of cartel members?

| Case | Cartel pairs | AUC of excess co-bidding |
|---|---:|---:|
| USA: Ohio school milk | 3 | 1.00 |
| Japan: Okinawa | 5,124 | 0.52 |
| Italy: Turin | 3,256 | 0.42 |
| Brazil: Petrobras | 102 | 0.38 |

And do the leads from the full group method land on cartel tenders?

| Case | Leads | Tenders flagged | Of which cartel tenders | Share of all tenders that are cartel tenders |
|---|---:|---:|---:|---:|
| Japan: Okinawa | 1 | 43 | 0% | 11% |
| USA: Ohio school milk | 3 | 319 | 3% | 13% |
| Brazil: Petrobras | 0 | 0 | | 33% |
| Italy: Turin | 0 | 0 | | 51% |

**They do not.** Who bids with whom reflects how a market is organised: which contractors are local, which are eligible, whom the buyer invites. Ohio shows both halves of this. The three cartel dairies are the three most closely linked pairs in that market, so the graph does point at them. But the group they sit in did not stand out on any outcome screen, and the leads that did form were elsewhere. The group method marks places where collusion would be easy to sustain. It does not mark places where it happened.

This is the reason the Assam output is framed the way it is.

## The Assam run

Source: [Assam Public Procurement Data](https://github.com/CivicDataLab/assam-tenders-data), published by CivicDataLab under the Open Database License. 43,669 tenders from fiscal years 2016-17 to 2022-23.

| | |
|---|---:|
| Tenders that list who bid | 9,994 |
| Distinct bidders (matched by name) | 12,349 |
| Pairs of bidders that ever bid together | 2,504,195 |
| Pairs linked: three or more joint tenders, and more than chance | 22,050 |
| Co-bidding groups found | 338 |
| Groups where the closed-group screen fired | 46 |
| Groups where the award-price screen fired | 10 |
| Groups where the cover-bidding screen fired | 8 |
| Groups where the rotation screen fired | 0 of 63 tested |
| **Leads: two or more screens** | **4** |

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/figures/groups-dark.svg">
  <img src="docs/figures/groups-light.svg" alt="Scatter plot of 338 co-bidding groups in the Assam data. Horizontal axis is exclusivity from 0 to 1, vertical axis is the number of joint tenders on a log scale. Most groups sit near zero exclusivity. Four leads are highlighted." width="820">
</picture>

Each dot is a group of firms that bid together far more than their activity explains. Most are what a local market looks like. The four highlighted groups are the leads.

One finding does not depend on any screen. Award prices in this data pile up at two values:

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/figures/award-price-dark.svg">
  <img src="docs/figures/award-price-light.svg" alt="Histogram of award value divided by the buyer's estimate for 4,012 Assam awards. Two tall spikes: 26 percent of awards at 0.90 of the estimate and 32 percent at 1.00." width="820">
</picture>

26% of awards are at 0.90 of the buyer's estimate and 32% are at 1.00, to the nearest 0.01. Piles like these usually come from rules, such as a floor below which a bid is treated as abnormally low. They are a property of the market, and a screen that read the price level on its own would flag half of it. The price screen here compares each group only with other tenders from the same buyer and postal region that drew the same number of bidders, because fewer bidders means awards nearer the estimate whether or not anyone colludes.

## Why not just ask an AI chatbot?

It is a fair question. General-purpose assistants such as ChatGPT or Gemini can explain bid rigging, summarise a tender notice and write code. Ask one "which of these firms are colluding?" and it will give an answer. The issue is what kind of answer that is.

A chatbot produces text that reads like an analysis. bidscreen performs the analysis. It computes every statistic from every bid and compares each one with a stated baseline. It also records how often each method has been right on cartels that were proven. When the question can end with a company under investigation, that difference decides whether the answer can be used at all.

| | General-purpose chatbot | bidscreen |
|---|---|---|
| How much data it reads | What fits in one conversation, far less than the 382 MB of JSON in the Assam data | All of it: 43,669 tenders and 2.5 million pairs of co-bidders |
| Where the numbers come from | Generated text, which can include figures that were never computed | Code covered by 112 tests. Five price screens match the published values to four decimals |
| Asked the same question twice | Can answer differently, and the model behind it is updated over time | Gives the same answer, from pinned data, fixed seeds and versioned code |
| How often it is right | Not known for this task | Measured on six documented cartels, failures included |
| Compared with what | Nothing, unless you build the baseline yourself | A stated null model for every screen |
| Showing its working | An explanation that is itself generated text | Every statistic, threshold and comparison group, in the report |
| Where the data goes | To the provider's servers, under its terms | Nowhere: it runs on your own computer |
| Naming companies | Will name them if asked, and can be confidently wrong | Never names one, and refuses to save a report that does |
| Cost | Free tiers are limited, and heavier use is paid | Free and open source. Runs offline on a laptop |

### What the difference looks like in practice

**It reads every bid, not a sample.** Collusion screening is a search for a few needles in a large haystack. The Assam run tests 2,504,195 pairs of bidders to find the 22,050 pairs that bid together more often than chance allows. Shown a few hundred rows, a chatbot will find patterns in those rows. It has no way to say whether they stand out from the other 43,000 tenders.

**"More than chance" needs a definition.** In a small district, the same five contractors meet on every tender because there are only five contractors. Someone reading the list, person or language model, sees a ring. A test that holds each firm's level of activity fixed sees an ordinary local market. bidscreen asks every question against a baseline:

- a hypergeometric test for each pair of firms;
- 20 reshuffled copies of the market that keep each firm's number of bids;
- for prices, a comparison only with tenders from the same buyer that drew as many bidders.

Of the 338 groups in Assam that bid together more than chance allows, 4 had two screens fire.

**Its record is published, failures included.** Every screen was scored on six cartels that courts and competition authorities documented. The price screens were then scored again, with each case held out of everything learned. The variance screen separates cartel tenders in four of the six cases. The co-bidding network singled out the cartel in one case of four. Those numbers tell a reviewer how much weight a lead can bear. No one can give the equivalent number for a chatbot answering the same question.

**The same input gives the same output.** Source files are pinned to a commit and checked against a SHA-256 digest, and every random step uses a fixed seed. Anyone can rerun `bidscreen screen assam` and get the same four leads. An answer that changes when the question is asked again, or when the provider updates its model, cannot be checked by a second reviewer, let alone defended.

**Every number can be traced.** For each lead, the report lists:

- which screens fired, and the statistic behind each;
- the p-value after correction for multiple testing, and the threshold it was held to;
- the tenders it was compared with;
- the ordinary explanations to rule out first.

[docs/methodology.md](docs/methodology.md) gives every formula and says where it departs from the paper it comes from. When a chatbot explains its own answer, the explanation is more generated text, not a record of a calculation.

**Names stay on your machine.** Raw tender files hold the names of firms and of individual contractors. Pasting them into a hosted chatbot sends them to a third party. bidscreen:

- runs locally;
- replaces every name with a keyed label;
- keeps the key out of the repository;
- refuses to write a report in which a real name appears.

For an audit office or a newsroom, that alone often settles the choice.

**It does not accuse.** Asked about a named company, a chatbot can produce a confident, specific claim that nothing supports. A wrong accusation of bid rigging can damage a business, and expose whoever repeats it. bidscreen is built so that it cannot make one. Its output is a reading list, and every lead says what to rule out. The wording is fixed in code, not left to a prompt.

### Could a chatbot just run this kind of analysis?

A chatbot with a code tool can write and run a script like this one. The question then becomes whether that script is right:

- Does the null model hold each firm's activity fixed?
- Are 2.5 million tests corrected for multiple testing?
- Does the price comparison control for the number of bidders?
- Do any names leak into the output?

Each of those took work here, and each is covered by tests. Writing a script is the quick part. Checking it is the real job, and in this repository it has been done in the open.

### Where a chatbot does help

The two work well together. A chatbot is good at:

- explaining what bid rotation or cover bidding means, or what an AUC measures;
- helping read the methodology, or adapting a loader to a new data source;
- drafting a note to a colleague about a lead, working from the anonymised report;
- suggesting innocent explanations to check before a lead goes any further.

Use bidscreen to find and measure, and a chatbot to help explain and write up. Give the chatbot the anonymised report, never the raw files.

## What this project will not do

A screen that publicly attached company names to the word "fraud" would be reckless, and wrong most of the time. So:

- **No names leave the tool.** Firms, tenders and buyers appear as `FIRM-00042`, `TENDER-00317`, `BUYER-0012`. Labels are derived with a keyed hash. The key stays in `data/private/`, which git ignores.
- **The report refuses to be written if a real name is in it.** The finished page is searched for every real identifier before it is saved. A test proves the refusal works.
- **The data is not redistributed.** Raw files hold real names of firms and of individual contractors. They are downloaded by the user, pinned to a commit and checked against a SHA-256 digest.
- **Every lead lists what to rule out first.** A small local market, a specialised trade, a stale estimate, a rule that piles bids at a floor.
- **Bidders are matched by name.** Two people who share a name are merged. A renamed firm is split. Nothing here should be acted on without going back to the tender records.

More in [docs/responsible-use.md](docs/responsible-use.md).

## Limits

- The per-case tables are in-sample. The held-out check learns on five cases and scores the sixth, but six cases are still six cases. It shows where a screen has carried signal. It does not promise the next market.
- The group method differs from Wachs and Kertesz (2019) in three stated ways, and its thresholds are judgement calls. Change them with command-line flags.
- The Assam bidder lists cover mostly 2021-22 and 2022-23, and the number of bidders listed matches the number the portal reports for under half of the tenders.
- No estimate of how many leads are false is possible on the Assam data, because there is no ground truth for it.

The single change that would matter most: the amount of every losing bid. With those, the screens in the first table apply directly.

## Project site

<a href="https://anubhavdey0.github.io/procurement-fraud-pattern-detector/"><img src="docs/figures/site-hero.png" alt="The project site's opening screen: the headline 'Leads for review. Never a verdict.' beside an animated bipartite graph of the planted cartel in the demo market." width="820"></a>

The site in [`site/`](site/) is built with React, Vite, Tailwind and Motion, and published to GitHub Pages by [`.github/workflows/site.yml`](.github/workflows/site.yml) on every push that touches it. It reads one file, `site/src/data/site-data.json`, which holds the same content as the HTML report: labels only, dates to the month. The file is written by

```bash
bidscreen export-site           # runs the Assam screen and writes site/src/data/site-data.json
```

and is put through the same leak check as the report, so it is not written if a real name is in it. To work on the site locally:

```bash
cd site
npm ci
npm run dev                     # http://localhost:5173
```

## Project layout

```
src/bidscreen/
  model.py            the two tables every loader produces
  ingest/             loaders: Assam OCDS package, six cartel cases, pinned downloads
  names.py            conservative supplier-name matching
  anonymize.py        keyed labels and the leak check
  graph.py            bipartite graph, co-bidding links, groups, reshuffle null model
  screens/            price, rotation, cover, award-price screens
  leads.py            runs the screens and assembles leads
  validate.py         scores screens against the documented cases
  charts.py           SVG charts with no plotting dependency
  report.py           the HTML report
  sitedata.py         the data file the project site reads
  synthetic.py        demo market with a planted cartel
  cli.py              the bidscreen command
tests/                107 tests, including hand-worked values for every statistic
docs/                 methodology, data sources, responsible use, sample output
site/                 the project site
```

## Data and licences

| Source | Used for | Licence |
|---|---|---|
| [CivicDataLab, Assam Public Procurement Data](https://github.com/CivicDataLab/assam-tenders-data) | the Assam run | Open Database License (ODbL) |
| Garcia Rodriguez et al. (2022), six collusion datasets | validation | published with the paper; not redistributed here |

Figures and the sample report in `docs/` contain information from the Assam Public Procurement Data, made available by CivicDataLab under the ODbL. Details in [docs/data-sources.md](docs/data-sources.md).

The code is under the MIT licence. See [LICENSE](LICENSE).

## References

- Abrantes-Metz, Froeb, Geweke and Taylor (2006). A variance screen for collusion. *International Journal of Industrial Organization* 24(3).
- Garcia Rodriguez, Rodriguez-Montequin, Ballesteros-Perez, Love and Signor (2022). Collusion detection in public procurement auctions with machine learning algorithms. *Automation in Construction* 133, 104047.
- Huber and Imhof (2019). Machine learning with screens for detecting bid-rigging cartels. *International Journal of Industrial Organization* 65.
- Imhof, Karagok and Rutz (2018). Screening for bid rigging: does it work? *Journal of Competition Law and Economics* 14(2).
- Lancaster (1961). Significance tests in discrete distributions. *Journal of the American Statistical Association* 56(294).
- Lancichinetti, Fortunato and Kertesz (2009). Detecting the overlapping and hierarchical community structure in complex networks. *New Journal of Physics* 11.
- Mood (1940). The distribution theory of runs. *Annals of Mathematical Statistics* 11(4).
- OECD (2009). Guidelines for fighting bid rigging in public procurement.
- Onnela, Saramaki, Kertesz and Kaski (2005). Intensity and coherence of motifs in weighted complex networks. *Physical Review E* 71.
- Toth, Fazekas, Czibik and Toth (2014). Toolkit for detecting collusive bidding in public procurement. Corruption Research Center Budapest.
- van Elteren (1960). On the combination of independent two-sample tests of Wilcoxon. *Bulletin of the International Statistical Institute* 37.
- Wachs and Kertesz (2019). A network approach to cartel detection in public auction markets. *Scientific Reports* 9, 10818.
- Youden (1950). Index for rating diagnostic tests. *Cancer* 3(1).
