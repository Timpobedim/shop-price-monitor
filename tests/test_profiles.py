from __future__ import annotations

import json
from pathlib import Path

import pytest

from shop_monitor.profiles import BUILTIN, Field, ProfileError, load_profile, parse_profile, resolve, to_json

GOOD = {
    "name": "shop",
    "url": "https://shop.example/catalog",
    "card": "div.product-card",
    "fields": {
        "name": ".product-card__title",
        "price": {"selector": ".product-card__price"},
        "rating": {"selector": ".rating", "attribute": "data-rating", "optional": True},
    },
    "next_page": "a.pagination__next",
}


def test_profile_from_json() -> None:
    profile = parse_profile(GOOD)
    assert profile.card == "div.product-card"
    assert profile.fields["name"] == Field(".product-card__title")
    assert profile.fields["rating"] == Field(".rating", "data-rating", True)
    assert profile.ready_selector == "div.product-card"


@pytest.mark.parametrize(
    ("broken", "message"),
    [
        ({**GOOD, "card": ""}, "не хватает ключей"),
        ({**GOOD, "fields": {"price": ".p"}}, "«name»"),
        ({**GOOD, "fields": {"name": ".n", "price": ".p", "цена": ".c"}}, "неизвестные поля"),
        ({**GOOD, "fields": {"name": {"attr": "title"}, "price": ".p"}}, "нужен CSS-селектор"),
        ([1, 2], "ожидается объект JSON"),
    ],
)
def test_mistakes_are_explained(broken: object, message: str) -> None:
    with pytest.raises(ProfileError, match=message):
        parse_profile(broken)


def test_load_and_resolve(tmp_path: Path) -> None:
    path = tmp_path / "профиль.json"
    path.write_text(json.dumps(GOOD, ensure_ascii=False), encoding="utf-8")
    assert load_profile(path).name == "shop"
    assert resolve(str(path)).name == "shop"
    assert resolve("books") is BUILTIN["books"]
    with pytest.raises(ProfileError, match="не найден"):
        resolve("ozon")
    broken = tmp_path / "битый.json"
    broken.write_text("{", encoding="utf-8")
    with pytest.raises(ProfileError, match="Не удалось прочитать"):
        load_profile(broken)


def test_to_json_is_loadable_back() -> None:
    assert parse_profile(json.loads(to_json(parse_profile(GOOD)))) == parse_profile(GOOD)
