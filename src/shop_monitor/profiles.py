"""Профиль сайта: где карточки и как в них лежат поля.

Селекторы вынесены из кода в данные, поэтому новый магазин добавляется JSON-файлом, а не правкой
парсера.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

FIELDS = ("name", "price", "availability", "rating", "link")
REQUIRED_FIELDS = ("name", "price")


class ProfileError(ValueError):
    """Профиль написан неправильно; текст — для пользователя."""


@dataclass(frozen=True)
class Field:
    selector: str
    attribute: str | None = None  # None — берём текст элемента
    optional: bool = False


@dataclass(frozen=True)
class Profile:
    name: str
    url: str
    card: str  # CSS-селектор карточки товара
    fields: dict[str, Field]
    next_page: str | None = None  # CSS-селектор ссылки «следующая страница»
    wait: str | None = None  # что ждать на странице; по умолчанию — карточка
    title: str = ""

    @property
    def ready_selector(self) -> str:
        return self.wait or self.card


BOOKS = Profile(
    name="books",
    title="Books to Scrape — учебная витрина для парсинга",
    url="https://books.toscrape.com/catalogue/category/books/mystery_3/index.html",
    card="article.product_pod",
    fields={
        "name": Field("h3 a", attribute="title"),
        "price": Field("p.price_color"),
        "availability": Field("p.availability", optional=True),
        "rating": Field("p.star-rating", attribute="class", optional=True),
        "link": Field("h3 a", attribute="href", optional=True),
    },
    next_page="li.next a",
)
BUILTIN = {profile.name: profile for profile in (BOOKS,)}


def demo_profile(base_url: str) -> Profile:
    """Профиль локальной демо-витрины: она поднимается из `shop_monitor.demo`."""
    return Profile(
        name="demo",
        title="Локальная демо-витрина",
        url=f"{base_url}/index.html",
        card="article.product",
        fields={
            "name": Field("h3 a", attribute="title"),
            "price": Field("p.price"),
            "availability": Field("p.stock", optional=True),
            "rating": Field("p.rating", attribute="data-rating", optional=True),
            "link": Field("h3 a", attribute="href", optional=True),
        },
        next_page="a.next",
    )


def _field(name: str, raw: Any) -> Field:
    if isinstance(raw, str):
        return Field(raw)
    if not isinstance(raw, dict) or not isinstance(raw.get("selector"), str):
        raise ProfileError(f"Поле «{name}»: нужен CSS-селектор строкой или объект с ключом «selector»")
    attribute = raw.get("attribute")
    if attribute is not None and not isinstance(attribute, str):
        raise ProfileError(f"Поле «{name}»: «attribute» должен быть строкой")
    return Field(raw["selector"], attribute, bool(raw.get("optional", False)))


def parse_profile(raw: Any, *, source: str = "профиль") -> Profile:
    if not isinstance(raw, dict):
        raise ProfileError(f"{source}: ожидается объект JSON с ключами «name», «url», «card», «fields»")
    missing = [key for key in ("name", "url", "card", "fields") if not raw.get(key)]
    if missing:
        raise ProfileError(f"{source}: не хватает ключей {', '.join(f'«{key}»' for key in missing)}")
    fields_raw = raw["fields"]
    if not isinstance(fields_raw, dict):
        raise ProfileError(f'{source}: «fields» — объект вида {{"name": "h3 a"}}')
    unknown = [key for key in fields_raw if key not in FIELDS]
    if unknown:
        known = ", ".join(FIELDS)
        raise ProfileError(f"{source}: неизвестные поля {', '.join(unknown)}; бывают только {known}")
    fields = {name: _field(name, value) for name, value in fields_raw.items()}
    for name in REQUIRED_FIELDS:
        if name not in fields:
            raise ProfileError(f"{source}: без поля «{name}» мониторить нечего")
    return Profile(
        name=str(raw["name"]),
        url=str(raw["url"]),
        card=str(raw["card"]),
        fields=fields,
        next_page=str(raw["next_page"]) if raw.get("next_page") else None,
        wait=str(raw["wait"]) if raw.get("wait") else None,
        title=str(raw.get("title", "")),
    )


def load_profile(path: Path) -> Profile:
    try:
        raw = json.loads(path.read_text("utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ProfileError(f"Не удалось прочитать профиль {path.name}: {exc}") from exc
    return parse_profile(raw, source=path.name)


def resolve(name: str) -> Profile:
    """Имя встроенного профиля или путь к JSON-файлу."""
    if name in BUILTIN:
        return BUILTIN[name]
    path = Path(name)
    if path.exists():
        return load_profile(path)
    known = ", ".join(BUILTIN)
    raise ProfileError(f"Профиль «{name}» не найден: есть встроенные ({known}) или путь к JSON-файлу")


def to_json(profile: Profile) -> str:
    data = asdict(profile)
    data["fields"] = {
        name: {key: value for key, value in values.items() if value not in (None, False)}
        for name, values in data["fields"].items()
    }
    return json.dumps(
        {key: value for key, value in data.items() if value not in (None, "")}, ensure_ascii=False, indent=2
    )
