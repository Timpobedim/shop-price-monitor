from __future__ import annotations

import pytest

from shop_monitor.parsing import parse_availability, parse_price, parse_rating


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2 490,00 ₽", (249_000, "RUB")),
        ("1 299 ₽", (129_900, "RUB")),
        ("£47.82", (4782, "GBP")),
        ("$1,139.54", (113_954, "USD")),
        ("1.199,00 €", (119_900, "EUR")),
        ("Цена: 890 руб.", (89_000, "RUB")),
        ("по запросу", (None, "")),
        ("", (None, "")),
    ],
)
def test_prices(text: str, expected: tuple[int | None, str]) -> None:
    assert parse_price(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("В наличии: 7 шт.", (True, 7)),
        ("в наличии", (True, None)),
        ("Нет в наличии", (False, None)),
        ("Out of stock", (False, None)),
        ("In stock (22 available)", (True, 22)),
        ("осталось 3", (True, 3)),
        ("", (None, None)),
        ("уточняйте", (None, None)),
    ],
)
def test_availability(text: str, expected: tuple[bool | None, int | None]) -> None:
    assert parse_availability(text) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("star-rating Three", 3.0),
        ("star-rating Five", 5.0),
        ("4,5", 4.5),
        ("4.2", 4.2),
        ("рейтинг 3", 3.0),
        ("", None),
        ("нет оценок", None),
    ],
)
def test_ratings(value: str, expected: float | None) -> None:
    assert parse_rating(value) == expected
