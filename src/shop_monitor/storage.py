"""История прогонов в SQLite: что и когда видел монитор.

История — база, а не CSV с дописанными строками: прогон, его товары, и по ним считается сравнение.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from shop_monitor.collect import Item

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile TEXT NOT NULL,
    url TEXT NOT NULL,
    started TEXT NOT NULL,
    finished TEXT NOT NULL,
    pages INTEGER NOT NULL,
    items INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS items (
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    name TEXT NOT NULL,
    price INTEGER,
    currency TEXT NOT NULL,
    available INTEGER,
    quantity INTEGER,
    rating REAL,
    url TEXT NOT NULL,
    position INTEGER NOT NULL,
    page INTEGER NOT NULL,
    PRIMARY KEY (run_id, key)
);
CREATE INDEX IF NOT EXISTS runs_profile ON runs(profile, id);
"""


@dataclass(frozen=True)
class Run:
    id: int
    profile: str
    url: str
    started: datetime
    finished: datetime
    pages: int
    items: int


def _moment(text: str) -> datetime:
    return datetime.fromisoformat(text)


@contextmanager
def connect(path: Path) -> Iterator[sqlite3.Connection]:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, isolation_level=None)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA)
        yield connection
    finally:
        connection.close()


def save_run(
    connection: sqlite3.Connection, profile: str, url: str, items: Sequence[Item], started: datetime, finished: datetime
) -> int:
    with closing(connection.cursor()) as cursor:
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            "INSERT INTO runs (profile, url, started, finished, pages, items) VALUES (?, ?, ?, ?, ?, ?)",
            (
                profile,
                url,
                started.isoformat(),
                finished.isoformat(),
                max((item.page for item in items), default=0),
                len(items),
            ),
        )
        run_id = int(cursor.lastrowid or 0)
        cursor.executemany(
            "INSERT OR REPLACE INTO items (run_id, key, name, price, currency, available, quantity, rating, url,"
            " position, page) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    run_id,
                    item.key,
                    item.name,
                    item.price,
                    item.currency,
                    None if item.available is None else int(item.available),
                    item.quantity,
                    item.rating,
                    item.url,
                    item.position,
                    item.page,
                )
                for item in items
            ],
        )
        cursor.execute("COMMIT")
    return run_id


def _run(row: sqlite3.Row) -> Run:
    return Run(
        id=int(row["id"]),
        profile=str(row["profile"]),
        url=str(row["url"]),
        started=_moment(str(row["started"])),
        finished=_moment(str(row["finished"])),
        pages=int(row["pages"]),
        items=int(row["items"]),
    )


def runs(connection: sqlite3.Connection, profile: str | None = None, limit: int = 20) -> list[Run]:
    if profile is None:
        rows = connection.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    else:
        rows = connection.execute(
            "SELECT * FROM runs WHERE profile = ? ORDER BY id DESC LIMIT ?", (profile, limit)
        ).fetchall()
    return [_run(row) for row in rows]


def items_of(connection: sqlite3.Connection, run_id: int) -> list[Item]:
    rows = connection.execute("SELECT * FROM items WHERE run_id = ? ORDER BY position", (run_id,)).fetchall()
    return [
        Item(
            key=str(row["key"]),
            name=str(row["name"]),
            price=None if row["price"] is None else int(row["price"]),
            currency=str(row["currency"]),
            available=None if row["available"] is None else bool(row["available"]),
            quantity=None if row["quantity"] is None else int(row["quantity"]),
            rating=None if row["rating"] is None else float(row["rating"]),
            url=str(row["url"]),
            position=int(row["position"]),
            page=int(row["page"]),
        )
        for row in rows
    ]


def previous_run(connection: sqlite3.Connection, profile: str, before: int) -> Run | None:
    row = connection.execute(
        "SELECT * FROM runs WHERE profile = ? AND id < ? ORDER BY id DESC LIMIT 1", (profile, before)
    ).fetchone()
    return None if row is None else _run(row)


def now() -> datetime:
    return datetime.now(UTC)
