"""Что изменилось с прошлого прогона: цены, наличие, состав витрины, позиции."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from shop_monitor.collect import Item

PRICE_UP = "подорожал"
PRICE_DOWN = "подешевел"
APPEARED = "появился"
DISAPPEARED = "исчез"
OUT_OF_STOCK = "закончился"
BACK_IN_STOCK = "снова в наличии"
ORDER = (PRICE_DOWN, PRICE_UP, OUT_OF_STOCK, BACK_IN_STOCK, APPEARED, DISAPPEARED)


@dataclass(frozen=True)
class Change:
    kind: str
    item: Item  # текущее состояние товара, а для исчезнувших — прошлое
    was: int | None = None  # цена в прошлом прогоне
    now: int | None = None

    @property
    def difference(self) -> int | None:
        return None if self.was is None or self.now is None else self.now - self.was

    @property
    def share(self) -> float | None:
        difference = self.difference
        return None if difference is None or not self.was else difference / self.was


def compare(previous: Sequence[Item], current: Sequence[Item]) -> list[Change]:
    before = {item.key: item for item in previous}
    after = {item.key: item for item in current}
    changes: list[Change] = []
    for key, item in after.items():
        was = before.get(key)
        if was is None:
            changes.append(Change(APPEARED, item, None, item.price))
            continue
        if was.price is not None and item.price is not None and was.price != item.price:
            kind = PRICE_UP if item.price > was.price else PRICE_DOWN
            changes.append(Change(kind, item, was.price, item.price))
        if was.available and item.available is False:
            changes.append(Change(OUT_OF_STOCK, item, was.price, item.price))
        elif was.available is False and item.available:
            changes.append(Change(BACK_IN_STOCK, item, was.price, item.price))
    for key, item in before.items():
        if key not in after:
            changes.append(Change(DISAPPEARED, item, item.price, None))
    changes.sort(key=lambda change: (ORDER.index(change.kind), -abs(change.difference or 0), change.item.name))
    return changes


def moved(previous: Sequence[Item], current: Sequence[Item]) -> dict[str, int]:
    """Насколько товар сдвинулся по витрине: минус — поднялся выше."""
    before = {item.key: item.position for item in previous}
    return {item.key: item.position - before[item.key] for item in current if item.key in before}
