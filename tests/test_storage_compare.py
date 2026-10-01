from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from shop_monitor.collect import Item
from shop_monitor.compare import (
    APPEARED,
    BACK_IN_STOCK,
    DISAPPEARED,
    OUT_OF_STOCK,
    PRICE_DOWN,
    PRICE_UP,
    compare,
    moved,
)
from shop_monitor.storage import connect, items_of, previous_run, runs, save_run

MOMENT = datetime(2026, 9, 12, 9, 0, tzinfo=UTC)


def item(key: str, price: int | None, *, available: bool | None = True, position: int = 1, page: int = 1) -> Item:
    return Item(
        key=key,
        name=key.title(),
        price=price,
        currency="RUB",
        available=available,
        quantity=3 if available else None,
        rating=4.5,
        url=f"https://shop.example/{key}",
        position=position,
        page=page,
    )


def test_changes_between_runs() -> None:
    before = [item("чайник", 249_000), item("блендер", 389_000), item("микроволновка", 799_000),
              item("сушилка", 459_000, available=False), item("термос", 159_000)]  # fmt: skip
    after = [item("чайник", 279_000), item("блендер", 344_000), item("микроволновка", 799_000, available=False),
             item("сушилка", 459_000), item("соковыжималка", 899_000)]  # fmt: skip
    changes = {change.kind: change for change in compare(before, after)}
    assert set(changes) == {PRICE_UP, PRICE_DOWN, OUT_OF_STOCK, BACK_IN_STOCK, APPEARED, DISAPPEARED}
    assert (changes[PRICE_UP].was, changes[PRICE_UP].now, changes[PRICE_UP].difference) == (249_000, 279_000, 30_000)
    assert changes[PRICE_DOWN].share is not None
    assert round(changes[PRICE_DOWN].share, 4) == round(-45_000 / 389_000, 4)
    assert changes[DISAPPEARED].item.name == "Термос"
    assert changes[APPEARED].item.name == "Соковыжималка"
    assert [change.kind for change in compare(before, after)][:2] == [PRICE_DOWN, PRICE_UP]


def test_first_run_shows_everything_as_new() -> None:
    changes = compare([], [item("чайник", 249_000)])
    assert [(change.kind, change.now) for change in changes] == [(APPEARED, 249_000)]


def test_positions_moved() -> None:
    before = [item("чайник", 1, position=1), item("блендер", 1, position=2)]
    after = [item("блендер", 1, position=1), item("чайник", 1, position=2), item("новый", 1, position=3)]
    assert moved(before, after) == {"блендер": -1, "чайник": 1}


def test_history_is_saved_and_read_back(tmp_path: Path) -> None:
    database = tmp_path / "история.sqlite"
    first = [item("чайник", 249_000, position=1), item("блендер", 389_000, position=2, page=1)]
    second = [item("чайник", 279_000, position=1)]
    with connect(database) as connection:
        first_id = save_run(connection, "demo", "http://shop", first, MOMENT, MOMENT)
        second_id = save_run(connection, "demo", "http://shop", second, MOMENT, MOMENT)
    with connect(database) as connection:  # база переживает закрытие
        assert [run.id for run in runs(connection, "demo")] == [second_id, first_id]
        saved = items_of(connection, first_id)
        assert saved == first
        previous = previous_run(connection, "demo", second_id)
        assert previous is not None
        assert previous.id == first_id
        assert previous_run(connection, "demo", first_id) is None
        assert runs(connection, "другой") == []
