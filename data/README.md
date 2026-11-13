# Data directory

Nothing in this directory is committed except this file. Git ignores the rest.

| Path | What goes there | Why it is ignored |
|---|---|---|
| `raw/` | files downloaded by `bidscreen fetch` | they hold real names of firms and of individual contractors, and are not this project's to redistribute |
| `interim/` | parsed tables cached by the Assam loader | same content as `raw/`, in another format |
| `private/` | `pseudonym.key`, created on first use | whoever holds the key can map labels such as `FIRM-00042` back to names |

To fill it:

```bash
bidscreen fetch            # everything
bidscreen fetch assam      # only the Assam tenders
bidscreen fetch labelled   # only the six cartel cases
```

Each file is pinned to a commit and checked against a SHA-256 digest. A file that does not match is deleted and the command stops.

Keep `private/pseudonym.key` if you want labels to stay the same from one run to the next. Delete it and the next run assigns new labels.

Sources and licences are described in [docs/data-sources.md](../docs/data-sources.md).
