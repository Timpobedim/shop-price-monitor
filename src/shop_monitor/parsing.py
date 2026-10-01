"""Разбор того, что видно на карточке: цена, наличие, рейтинг.

Отдельный модуль без браузера: эти правила проверяются обычными тестами, а не через Selenium.
Числа берутся по смыслу, а не по номеру символа в тексте: пробел или двузначное число разбор не ломают.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

CURRENCIES = {"₽": "RUB", "руб": "RUB", "р.": "RUB", "£": "GBP", "$": "USD", "€": "EUR", "₸": "KZT", "¥": "JPY"}
WORD_RATINGS = {
    "one": 1.0, "two": 2.0, "three": 3.0, "four": 4.0, "five": 5.0,
    "один": 1.0, "два": 2.0, "три": 3.0, "четыре": 4.0, "пять": 5.0,
}  # fmt: skip
IN_STOCK = ("в наличии", "есть в наличии", "in stock", "на складе", "available")
OUT_OF_STOCK = ("нет в наличии", "нет на складе", "out of stock", "распродан", "закончил", "недоступен")
_NUMBER = re.compile(r"-?\d[\d  .,']*")
_SPACES = re.compile(r"[\s  ']")


def normalize(text: str) -> str:
    return " ".join(text.replace("ё", "е").lower().split())


def parse_price(text: str) -> tuple[int | None, str]:
    """«1 299,00 ₽» → (129900, «RUB»), «£47.82» → (4782, «GBP»). Нет числа → (None, валюта или «»)."""
    lowered = text.lower()
    currency = next((code for sign, code in CURRENCIES.items() if sign in lowered), "")
    match = _NUMBER.search(text)
    if match is None:
        return None, currency
    number = _SPACES.sub("", match.group())
    if "," in number and "." in number:  # десятичный разделитель — тот, что правее
        number = (
            number.replace(".", "").replace(",", ".")
            if number.rfind(",") > number.rfind(".")
            else number.replace(",", "")
        )
    elif number.count(",") == 1:
        number = number.replace(",", ".")
    elif number.count(".") > 1:
        number = number.replace(".", "")
    try:
        return int(Decimal(number) * 100), currency
    except (InvalidOperation, ValueError):
        return None, currency


def parse_availability(text: str) -> tuple[bool | None, int | None]:
    """«В наличии: 7 шт.» → (True, 7); «Out of stock» → (False, None); непонятный текст → (None, None)."""
    lowered = normalize(text)
    if not lowered:
        return None, None
    available: bool | None = None
    if any(words in lowered for words in OUT_OF_STOCK):
        available = False
    elif any(words in lowered for words in IN_STOCK):
        available = True
    quantity = None
    match = re.search(r"\d+", lowered)
    if match and available is not False:
        quantity = int(match.group())
        available = True if available is None else available
    return available, quantity


def parse_rating(value: str) -> float | None:
    """«star-rating Three» → 3.0, «4,5» → 4.5, «data-rating=«2»» → 2.0. Не число и не слово → None."""
    lowered = normalize(value)
    for word, rating in WORD_RATINGS.items():
        if re.search(rf"\b{word}\b", lowered):
            return rating
    match = re.search(r"\d+(?:[.,]\d+)?", lowered)
    if match is None:
        return None
    return float(match.group().replace(",", "."))
