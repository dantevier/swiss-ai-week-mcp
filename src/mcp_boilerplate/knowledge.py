"""Local SQLite knowledge base and OpenAI passage embeddings."""

import asyncio
import json
import os
import re
import shutil
import sqlite3
import tempfile
import urllib.request
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from .config.settings import settings
from .sources import SOURCES

MODEL = "text-embedding-3-small"
SEED = Path(__file__).with_name("knowledge_seed.sqlite3")


def split_passages(markdown: str) -> list[str]:
    """Keep verbatim, overlapping excerpts below the embedding input limit."""
    text = markdown.strip()
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + 2200, len(text))
        if end < len(text):
            boundary = max(text.rfind(" ", start + 1700, end), text.rfind("\n", start + 1700, end))
            if boundary > start:
                end = boundary + 1
        chunks.append(text[start:end].strip())
        if end == len(text):
            break
        start = max(start + 1, end - 200)
    return chunks


class OpenAIEmbedder:
    """Use the same model for stored passages and live queries."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self._embed, texts)

    @staticmethod
    def _embed(texts: list[str]) -> list[list[float]]:
        key = settings.openai_api_key
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        vectors = []
        for start in range(0, len(texts), 50):
            batch = texts[start : start + 50]
            request = urllib.request.Request(
                "https://api.openai.com/v1/embeddings",
                data=json.dumps({"model": MODEL, "input": batch}).encode(),
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    data = json.load(response)
                ordered = sorted(data["data"], key=lambda item: item["index"])
                result = [item["embedding"] for item in ordered]
                if len(result) != len(batch) or any(len(vector) != 1536 for vector in result):
                    raise ValueError("Unexpected embedding response")
                vectors.extend(result)
            except (OSError, KeyError, ValueError, TypeError) as exc:
                raise RuntimeError("OpenAI embeddings are unavailable") from exc
        return vectors


class KnowledgeBase:
    """Store the latest validated crawl for each approved source."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path is not None else Path(
            settings.knowledge_db_path or Path.home() / ".swiss-ai-week-mcp" / "knowledge.sqlite3"
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if path is None and not self.path.exists() and SEED.exists():
            # ponytail: direct scan and one local file suit <100 pages; add a vector index if scale changes.
            with tempfile.NamedTemporaryFile(dir=self.path.parent, delete=False) as temp:
                temp_path = Path(temp.name)
            try:
                shutil.copyfile(SEED, temp_path)
                try:
                    os.link(temp_path, self.path)
                except FileExistsError:
                    pass
            finally:
                temp_path.unlink(missing_ok=True)
        with self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS sources (
                    level TEXT NOT NULL, source TEXT NOT NULL, authority TEXT NOT NULL,
                    url TEXT NOT NULL, crawled_at TEXT NOT NULL, markdown TEXT NOT NULL,
                    metadata TEXT NOT NULL, embedding_model TEXT NOT NULL,
                    PRIMARY KEY (level, source)
                );
                CREATE TABLE IF NOT EXISTS passages (
                    id INTEGER PRIMARY KEY, level TEXT NOT NULL, source TEXT NOT NULL,
                    ordinal INTEGER NOT NULL, text TEXT NOT NULL, embedding TEXT NOT NULL,
                    FOREIGN KEY (level, source) REFERENCES sources(level, source) ON DELETE CASCADE
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS passages_fts
                    USING fts5(text, level UNINDEXED, source UNINDEXED);
                CREATE TABLE IF NOT EXISTS failures (
                    level TEXT NOT NULL, source TEXT NOT NULL, failed_at TEXT NOT NULL,
                    error TEXT NOT NULL, PRIMARY KEY (level, source)
                );
                """
            )

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def save(self, record: dict, chunks: list[str], vectors: list[list[float]]) -> None:
        if not chunks or len(chunks) != len(vectors):
            raise ValueError("Missing passage embeddings")
        level, source = record["authority_level"], record["source"]
        with self.connect() as db:
            db.execute(
                "DELETE FROM passages_fts WHERE rowid IN "
                "(SELECT id FROM passages WHERE level = ? AND source = ?)",
                (level, source),
            )
            db.execute("DELETE FROM passages WHERE level = ? AND source = ?", (level, source))
            db.execute(
                """
                INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(level, source) DO UPDATE SET
                    authority=excluded.authority, url=excluded.url,
                    crawled_at=excluded.crawled_at, markdown=excluded.markdown,
                    metadata=excluded.metadata, embedding_model=excluded.embedding_model
                """,
                (
                    level, source, record["authority"], record["url"], record["crawled_at"],
                    record["markdown"], json.dumps(record.get("metadata", {})), MODEL,
                ),
            )
            for ordinal, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
                cursor = db.execute(
                    "INSERT INTO passages (level, source, ordinal, text, embedding) VALUES (?, ?, ?, ?, ?)",
                    (level, source, ordinal, chunk, json.dumps(vector, separators=(",", ":"))),
                )
                db.execute(
                    "INSERT INTO passages_fts (rowid, text, level, source) VALUES (?, ?, ?, ?)",
                    (cursor.lastrowid, chunk, level, source),
                )
            db.execute("DELETE FROM failures WHERE level = ? AND source = ?", (level, source))

    def failed(self, level: str, source: str, error: str) -> None:
        with self.connect() as db:
            db.execute(
                """
                INSERT INTO failures VALUES (?, ?, ?, ?)
                ON CONFLICT(level, source) DO UPDATE SET
                    failed_at=excluded.failed_at, error=excluded.error
                """,
                (level, source, datetime.now(UTC).isoformat(), error),
            )

    def get(self, level: str, source: str) -> dict:
        if level not in SOURCES or source not in SOURCES[level]:
            raise ValueError("Unknown approved source")
        with self.connect() as db:
            row = db.execute(
                """
                SELECT s.*, f.failed_at AS refresh_failed_at, f.error AS refresh_error
                FROM sources s LEFT JOIN failures f USING (level, source)
                WHERE s.level = ? AND s.source = ?
                """,
                (level, source),
            ).fetchone()
        if row is None or row["url"] != SOURCES[level][source].url:
            raise ValueError("Source has not been crawled")
        result = dict(row)
        result["metadata"] = json.loads(result["metadata"])
        return result

    async def search(self, query: str, limit: int = 5, embedder=None) -> dict:
        query = query.strip()
        if not query or len(query) > 500:
            raise ValueError("Query must contain 1 to 500 characters")
        if not 1 <= limit <= 10:
            raise ValueError("Limit must be between 1 and 10")
        try:
            vector = (await (embedder or OpenAIEmbedder()).embed([query]))[0]
        except RuntimeError:
            return {"method": "keyword_fallback", "results": self._keyword(query, limit)}
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT p.text, p.embedding, s.level, s.source, s.authority, s.url,
                       s.crawled_at, f.failed_at AS refresh_failed_at
                FROM passages p JOIN sources s USING (level, source)
                LEFT JOIN failures f USING (level, source)
                WHERE s.embedding_model = ?
                """,
                (MODEL,),
            ).fetchall()
        scored = []
        for row in rows:
            if not self._approved(row):
                continue
            saved = json.loads(row["embedding"])
            if len(saved) != len(vector):
                continue
            score = sum(a * b for a, b in zip(vector, saved, strict=True))
            scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        return {
            "method": "semantic",
            "results": [self._result(row, round(score, 4)) for score, row in scored[:limit]],
        }

    def _keyword(self, query: str, limit: int) -> list[dict]:
        terms = re.findall(r"\w+", query)[:20]
        if not terms:
            return []
        match = " OR ".join(f'"{term}"' for term in terms)
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT p.text, s.level, s.source, s.authority, s.url, s.crawled_at,
                       f.failed_at AS refresh_failed_at
                FROM passages_fts ft JOIN passages p ON p.id = ft.rowid
                JOIN sources s ON s.level = p.level AND s.source = p.source
                LEFT JOIN failures f ON f.level = s.level AND f.source = s.source
                WHERE passages_fts MATCH ? ORDER BY bm25(passages_fts) LIMIT 50
                """,
                (match,),
            ).fetchall()
        return [self._result(row) for row in rows if self._approved(row)][:limit]

    @staticmethod
    def _approved(row: sqlite3.Row) -> bool:
        level, source = row["level"], row["source"]
        return level in SOURCES and source in SOURCES[level] and SOURCES[level][source].url == row["url"]

    @staticmethod
    def _result(row: sqlite3.Row, score: float | None = None) -> dict:
        result = {
            "level": row["level"], "source": row["source"], "authority": row["authority"],
            "url": row["url"], "crawled_at": row["crawled_at"],
            "passage": row["text"], "refresh_failed_at": row["refresh_failed_at"],
        }
        if score is not None:
            result["score"] = score
        return result
