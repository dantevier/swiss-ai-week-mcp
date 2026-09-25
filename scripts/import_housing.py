"""Import BWO/UFAB housing knowledge (P0/P1) from JSON into the local SQLite DB.

    python scripts/import_housing.py                   offline import of the seed
    python scripts/import_housing.py --verify-sources  refetch sources, check every
                                                       passage, record fetched_at

--verify-sources needs network access and pypdf. It writes fetched_at into the
seed only for sources whose passages were all found; the import refuses records
whose source has never been verified, so scraped_at is never invented.
"""

import argparse
import hashlib
import io
import json
import re
import sqlite3
import urllib.request
from contextlib import closing
from datetime import UTC, date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "housing_knowledge.json"
SCHEMA = ROOT / "src" / "mcp_swiss_info" / "storage" / "migrations" / "003_housing_knowledge.sql"
DEFAULT_DATABASE = ROOT / "var" / "swissproject.sqlite3"
USER_AGENT = "swiss-grounding-mcp/0.1 (Swiss AI Weeks hackathon; contact via repo)"
PASSAGE_SEPARATOR = "\n[…]\n"
CANONICAL_LANGUAGE = "it"
INHERITED = ("record_kind", "topic", "data", "jurisdiction_level", "effective_from", "applicability_verified")
RECORD_KINDS = {"rate_publication", "faq", "guidance", "jurisdiction"}
JURISDICTION_LEVELS = {"federal", "cantonal", "municipal", "mixed"}
RATE_KEYS = {
    "reference_rate_bp", "average_rate_bp", "average_rate_as_of", "value_unchanged_since",
    "next_publication_on", "official_publication_frequency",
}
# Columns that define the record's meaning; timestamps are excluded from the hash.
CONTENT_COLUMNS = (
    "item_key", "record_kind", "topic", "language", "title", "summary", "source_passage",
    "data_json", "conditions_json", "jurisdiction_level", "source_kind", "source_url",
    "source_locator", "source_version_date", "published_on", "effective_from",
    "applicability_verified",
)
COLUMNS = (
    *CONTENT_COLUMNS, "scraped_at", "last_verified_at", "last_changed_at",
    "refresh_interval_seconds", "next_check_at", "content_sha256", "parser_version",
)


def utc_timestamp(value: str) -> datetime:
    if not value.endswith("Z"):
        raise ValueError(f"Timestamp must be UTC with Z: {value!r}")
    return datetime.fromisoformat(value)


def load_seed() -> dict:
    return json.loads(SEED.read_text(encoding="utf-8"))


def build_rows(seed: dict) -> list[dict]:
    sources = seed["sources"]
    canonical = {record["item_key"]: record for record in seed["records"] if record["language"] == CANONICAL_LANGUAGE}
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for variant in seed["records"]:
        key = variant["item_key"]
        if key not in canonical:
            raise ValueError(f"{key}: variant without canonical {CANONICAL_LANGUAGE} record")
        # Variants share the language-neutral facts of the canonical record.
        record = {**{field: canonical[key][field] for field in INHERITED}, **variant}
        if (key, record["language"]) in seen:
            raise ValueError(f"Duplicate item_key/language: {key}/{record['language']}")
        seen.add((key, record["language"]))
        source = sources[record["source"]]
        if source["language"] != record["language"]:
            raise ValueError(f"{key}: record language differs from source {record['source']}")
        if not source.get("fetched_at"):
            raise ValueError(f"{key}: source {record['source']} never verified; run --verify-sources")
        if record["record_kind"] not in RECORD_KINDS or record["jurisdiction_level"] not in JURISDICTION_LEVELS:
            raise ValueError(f"{key}: invalid record_kind or jurisdiction_level")
        if not all(record.get(field) for field in ("title", "summary", "source_locator", "source_passage")):
            raise ValueError(f"{key}: missing title, summary, locator or passage")
        if record["record_kind"] == "rate_publication":
            data = record["data"]
            if set(data) != RATE_KEYS or not all(isinstance(data[k], int) for k in ("reference_rate_bp", "average_rate_bp")):
                raise ValueError(f"{key}: rate payload must have exactly {sorted(RATE_KEYS)} with integer bp")
            for field in ("average_rate_as_of", "value_unchanged_since", "next_publication_on"):
                date.fromisoformat(data[field])
        for field in ("effective_from",):
            if record.get(field):
                date.fromisoformat(record[field])
        for field in ("source_version_date", "published_on"):
            if source.get(field):
                date.fromisoformat(source[field])

        fetched_at = source["fetched_at"]
        interval = source["refresh_interval_seconds"]
        next_check = utc_timestamp(fetched_at) + timedelta(seconds=interval)
        row = {
            "item_key": key,
            "record_kind": record["record_kind"],
            "topic": record["topic"],
            "language": record["language"],
            "title": record["title"],
            "summary": record["summary"],
            "source_passage": PASSAGE_SEPARATOR.join(record["source_passage"]),
            "data_json": json.dumps(record["data"], ensure_ascii=False, sort_keys=True),
            "conditions_json": json.dumps(record["conditions"], ensure_ascii=False, sort_keys=True),
            "jurisdiction_level": record["jurisdiction_level"],
            "source_kind": source["source_kind"],
            "source_url": source["url"],
            "source_locator": record["source_locator"],
            "source_version_date": source["source_version_date"],
            "published_on": source["published_on"],
            "effective_from": record["effective_from"],
            "applicability_verified": int(record["applicability_verified"]),
            "scraped_at": fetched_at,
            "last_verified_at": fetched_at,
            "last_changed_at": fetched_at,
            "refresh_interval_seconds": interval,
            "next_check_at": next_check.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "parser_version": seed["_meta"]["parser_version"],
        }
        content = json.dumps([row[column] for column in CONTENT_COLUMNS], ensure_ascii=False)
        row["content_sha256"] = hashlib.sha256(content.encode("utf-8")).hexdigest()
        rows.append(row)
    return rows


def import_rows(database: Path) -> int:
    rows = build_rows(load_seed())
    database.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database)) as connection:
        connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        existing = {
            (item_key, language): (row_id, sha)
            for row_id, item_key, language, sha in connection.execute(
                "SELECT id, item_key, language, content_sha256 FROM housing_knowledge WHERE is_current = 1"
            )
        }
        with connection:
            for row in rows:
                current = existing.get((row["item_key"], row["language"]))
                if current is None:
                    connection.execute(
                        f"INSERT INTO housing_knowledge ({', '.join(COLUMNS)}) "
                        f"VALUES ({', '.join(':' + column for column in COLUMNS)})",
                        row,
                    )
                elif current[1] == row["content_sha256"]:
                    # Unchanged content: only verification and scheduling metadata move.
                    connection.execute(
                        "UPDATE housing_knowledge SET scraped_at = :scraped_at, "
                        "last_verified_at = :last_verified_at, next_check_at = :next_check_at, "
                        "refresh_interval_seconds = :refresh_interval_seconds WHERE id = :id",
                        {**row, "id": current[0]},
                    )
                else:
                    # Correction of the same fact: keep the old revision for audit.
                    connection.execute("UPDATE housing_knowledge SET is_current = 0 WHERE id = ?", (current[0],))
                    connection.execute(
                        f"INSERT INTO housing_knowledge (revision, {', '.join(COLUMNS)}) "
                        f"SELECT MAX(revision) + 1, {', '.join(':' + column for column in COLUMNS)} "
                        "FROM housing_knowledge WHERE item_key = :item_key AND language = :language",
                        row,
                    )
    return len(rows)


class _TextExtractor(HTMLParser):
    BLOCKS = {"p", "li", "h1", "h2", "h3", "h4", "div", "br", "tr", "summary", "button", "td"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in ("script", "style", "noscript"):
            self.skip += 1
        if tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript"):
            self.skip -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def source_text(body: bytes, source_format: str) -> str:
    if source_format == "html":
        extractor = _TextExtractor()
        extractor.feed(body.decode("utf-8"))
        return normalize("".join(extractor.parts))
    from pypdf import PdfReader  # only needed for verification

    pages = [page.extract_text() or "" for page in PdfReader(io.BytesIO(body)).pages]
    # Rejoin words hyphenated across PDF line breaks.
    return normalize(re.sub(r"-[ \t]*\n\s*", "", "\n".join(pages)))


def fetch(url: str, source_format: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        content_type = response.headers.get_content_type()
        expected = "text/html" if source_format == "html" else "application/pdf"
        if response.status != 200 or content_type != expected or response.url != url:
            raise ValueError(f"{url}: HTTP {response.status} {content_type} at {response.url}")
        body = response.read()
    if len(body) > 20_000_000:
        raise ValueError(f"{url}: response larger than 20 MB")
    return body


def verify_sources() -> bool:
    seed = load_seed()
    all_ok = True
    for source_id, source in seed["sources"].items():
        body = fetch(source["url"], source["format"])
        fetched_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        text = source_text(body, source["format"])
        missing = [
            (record["item_key"], index)
            for record in seed["records"] if record["source"] == source_id
            for index, segment in enumerate(record["source_passage"])
            if normalize(segment) not in text
        ]
        if missing:
            all_ok = False
            print(f"{source_id} FAILED: passages not found {missing}; fetched_at kept")
            continue
        source["fetched_at"] = fetched_at
        count = sum(record["source"] == source_id for record in seed["records"])
        print(f"{source_id} OK: {count} records verified at {fetched_at}")
    SEED.write_text(json.dumps(seed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return all_ok


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE, help=f"SQLite file (default: {DEFAULT_DATABASE})")
    parser.add_argument("--verify-sources", action="store_true", help="refetch sources and check passages")
    args = parser.parse_args()
    if args.verify_sources and not verify_sources():
        raise SystemExit("Source verification failed; database not updated")
    count = import_rows(args.database)
    print(f"Imported {count} housing records into {args.database.resolve()}")


if __name__ == "__main__":
    main()
