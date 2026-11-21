"""Download the public source files into ``data/raw``.

Nothing is redistributed with this repository. Each file is fetched from a
public location, pinned to a specific commit, and checked against a SHA-256
digest, so a changed or tampered file is refused and not silently used.

The cartel case files are mirrored from a public repository that holds the
supplementary material of Garcia Rodriguez et al. (2022). If the mirror goes
away, the files can be obtained from the paper and placed in
``data/raw/labelled`` under the same names.
"""

from __future__ import annotations

import hashlib
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

_RAW = "https://raw.githubusercontent.com"


class DownloadError(RuntimeError):
    """A source file could not be fetched, or did not match its digest."""


_ASSAM = f"{_RAW}/CivicDataLab/assam-tenders-data/1e12e516748130c15398b2501fb092bfa7413941"
_CASES = f"{_RAW}/aparmendariz/master_thesis/588755793f72b46aba2a55a40bd7217dc6685909"


@dataclass(frozen=True)
class Source:
    group: str
    path: str  # relative to the raw data directory
    url: str
    sha256: str


SOURCES = [
    Source(
        "assam",
        "assam/ocds_mapped_data.json.zip",
        f"{_ASSAM}/data/ProcessedData/ocds-mapped-data/current/ocds_mapped_data.json.zip",
        "c1f8de1058b0203d521d13423fe346d4011bfc824a27ac0f623c76c7de3a7019",
    ),
    Source(
        "labelled",
        "labelled/2.Brazil.xlsx",
        f"{_CASES}/2.Brazil.xlsx",
        "8b9ebc1b43700ab6a9e37784e9e27e464ebde6522be518a669f2ef90be6c4539",
    ),
    Source(
        "labelled",
        "labelled/3.GR_and_See-Gaster.xlsx",
        f"{_CASES}/3.GR_and_See-Gaster.xlsx",
        "3d3014cf4b10e498f81232d6b0f2830ccdeddf217907b30cd642bb128d80a2ac",
    ),
    Source(
        "labelled",
        "labelled/4.Italy.xlsx",
        f"{_CASES}/4.Italy.xlsx",
        "29be7641bfc37660997443062a1183d467500976997ab19e0e359281fbbb20b7",
    ),
    Source(
        "labelled",
        "labelled/5.Japan.xlsx",
        f"{_CASES}/5.Japan.xlsx",
        "40630b729ea6b83e21cf09faf55cc14624fad6a88d5ca73c0f11a90f4e2dbe88",
    ),
    Source(
        "labelled",
        "labelled/6.Ticino.xlsx",
        f"{_CASES}/6.Ticino.xlsx",
        "5e57081e7da2337ab7e7d1edff74cfe7173b7e621c5b08119840aacf297b20c5",
    ),
    Source(
        "labelled",
        "labelled/7.America.xlsx",
        f"{_CASES}/7.America.xlsx",
        "8f7270fcf3e70370b62b1620ac12234ec1a7f0c0ee930668cc45ca9ac7a8a82b",
    ),
]


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(group: str = "all", raw_dir: Path | str = "data/raw", log=print) -> list[Path]:
    """Download every source in ``group`` ("assam", "labelled" or "all").

    Files already present with the right digest are left alone.
    """
    raw_dir = Path(raw_dir)
    wanted = [s for s in SOURCES if group in ("all", s.group)]
    if not wanted:
        raise ValueError(f"unknown source group {group!r}")
    done = []
    for source in wanted:
        target = raw_dir / source.path
        if target.exists() and sha256_of(target) == source.sha256:
            log(f"ok        {source.path}")
            done.append(target)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix(target.suffix + ".part")
        log(f"download  {source.path}")
        request = urllib.request.Request(source.url, headers={"User-Agent": "bidscreen"})
        try:
            with (
                urllib.request.urlopen(request, timeout=120) as response,
                partial.open("wb") as out,
            ):
                while chunk := response.read(1 << 20):
                    out.write(chunk)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            partial.unlink(missing_ok=True)
            reason = getattr(error, "reason", None) or error
            raise DownloadError(
                f"{source.path}: download failed ({reason}). Check the connection and run "
                "`bidscreen fetch` again; files already downloaded are kept."
            ) from error
        digest = sha256_of(partial)
        if digest != source.sha256:
            partial.unlink()
            raise DownloadError(
                f"{source.path}: checksum mismatch (got {digest}). The file was not kept."
            )
        partial.replace(target)
        done.append(target)
    return done
