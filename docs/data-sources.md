# Data sources

No data is stored in this repository. `bidscreen fetch` downloads each file from a public location, pinned to a specific commit, and refuses any file whose SHA-256 digest does not match the one recorded in `src/bidscreen/ingest/download.py`.

## Why not the obvious sources

The first plan for this project assumed features that public tender data does not have.

| Wanted | Why it is not available |
|---|---|
| Bidders sharing an IP address | Portal telemetry. Never published. |
| Bidders registered on the same date or at the same address | Company registry lookups are paid and rate-limited. |
| Bulk tender data from GeM | Not offered as a bulk download. |
| Award data from the Central Public Procurement Portal | No bulk download of per-award records was found. The portal's published statistics are monthly summaries by organisation, and its tender search is protected by a captcha. |

What is available in bulk, with a clear licence and per-tender bidder lists, is the Assam data below. The project is built on what that data has.

## Assam Public Procurement Data

- **Publisher:** CivicDataLab, with the Finance Department of the Government of Assam and the Open Contracting Partnership.
- **Location:** https://github.com/CivicDataLab/assam-tenders-data
- **File used:** `data/ProcessedData/ocds-mapped-data/current/ocds_mapped_data.json.zip`
- **Licence:** Open Database License (ODbL) for the data.
- **Origin:** scraped by CivicDataLab from the state e-procurement portal and mapped to the Open Contracting Data Standard.
- **Coverage:** 43,669 tenders, fiscal years 2016-17 to 2022-23.

### What it has

| Field | Coverage | Used for |
|---|---|---|
| Buyer and procuring entity | all tenders | market segment |
| PIN code | all tenders with bidder lists | market segment |
| Estimated value | 85% of tenders | relative price |
| Bid opening date | all tenders | time order |
| Bidder names and the stage each bid reached | 9,994 tenders, almost all from 2021-22 and 2022-23 | the bipartite graph |
| Awarded supplier and award value | 5,258 tenders | winners, relative price |

### What it does not have

- **The amount of each losing bid.** This is the field the price screens need. Its absence is the main limit on what can be said about this market.
- **A stable bidder identifier.** Bidders are names. Many are individual contractors.
- **Complete bidder lists.** The number of bidders listed equals the number the portal reports for 44% of tenders with a list.

### Quirks handled by the loader

- Single objects are wrapped in one-element lists (`tender`, `buyer`, `value`).
- Dates are written year-day-month.
- If an award names a supplier that is missing from the tender's bidder list, the supplier is added as a bidder, because a firm must have bid to win. The current file has no such case.
- 236 tenders are split across several awards. They have no single award value and are left out of the price screen.

## Six documented cartel cases

- **Assembled by:** Garcia Rodriguez, Rodriguez-Montequin, Ballesteros-Perez, Love and Signor (2022), "Collusion detection in public procurement auctions with machine learning algorithms", *Automation in Construction* 133, 104047, doi:10.1016/j.autcon.2021.104047.
- **Downloaded from:** a public repository that mirrors the paper's supplementary files, pinned to a commit. If the mirror disappears, obtain the files from the paper and place them in `data/raw/labelled/` under the same names.
- **Licence:** published with the paper. The files are not redistributed here. Only aggregate statistics computed from them appear in this repository.

| Case | Tenders | Bids | Bidders identified | Award rule | Notes |
|---|---:|---:|---|---|---|
| Switzerland: Ticino | 224 | 1,629 | no | lowest bid | road construction cartel |
| Switzerland: Graubunden and See-Gaster | 4,344 | 21,231 | no | lowest bid | cartel members bid alongside outsiders in about 40% of tenders |
| Japan: Okinawa | 1,080 | 13,510 | yes | lowest bid in 83% of tenders | tenders before and after the competition authority's inspection |
| Brazil: Petrobras | 101 | 683 | yes | lowest bid | tenders examined in Operation Car Wash |
| Italy: Turin | 278 | 20,286 | yes | closest to a trimmed mean | about 70 bidders per tender |
| USA: Ohio school milk | 3,754 | 7,004 | yes | lowest bid | most tenders have two bidders |

Bidders appear only as the numeric ids the files already use. One file carries company names in a separate column. The loader drops that column on read, and a test checks that it does.

## Adding a source

Write a loader that returns a `bidscreen.model.Market`: a `tenders` frame and a `bids` frame with the columns listed at the top of `src/bidscreen/model.py`. Fill what the source has. Everything downstream works from those two tables.

A source that publishes the amount of every bid would make the price screens available, and those are the screens with evidence behind them.
