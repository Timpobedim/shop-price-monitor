"""Сбор проверяется на локальной витрине: настоящий браузер, но без интернета."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from conftest import Shop
from selenium.webdriver.remote.webdriver import WebDriver

from shop_monitor.collect import CollectError, collect
from shop_monitor.profiles import Field, demo_profile

pytestmark = pytest.mark.browser


def test_collects_every_page_in_order(driver: WebDriver, shop: Shop) -> None:
    items = collect(driver, demo_profile(shop.url), pause=0, sleep=lambda _: None)
    assert len(items) == 12
    assert [item.position for item in items] == list(range(1, 13))
    assert [item.page for item in items[:7]] == [1] * 6 + [2]
    first = items[0]
    assert first.name == "Чайник электрический 1,7 л"
    assert (first.price, first.currency) == (249_000, "RUB")
    assert (first.available, first.quantity, first.rating) == (True, 7, 4.5)
    assert first.url.endswith("product-KT-01.html")
    out_of_stock = next(item for item in items if item.name.startswith("Сушилка"))
    assert (out_of_stock.available, out_of_stock.quantity) == (False, None)


def test_waits_for_cards_and_respects_max_pages(driver: WebDriver, shop: Shop) -> None:
    pauses: list[float] = []
    items = collect(driver, demo_profile(shop.url), max_pages=1, pause=0.7, sleep=pauses.append)
    assert len(items) == 12 // 2
    assert pauses == []  # пауза нужна только перед переходом на следующую страницу
    items = collect(driver, demo_profile(shop.url), max_pages=2, pause=0.7, sleep=pauses.append)
    assert len(items) == 12
    assert pauses == [0.7]


def test_optional_field_may_be_missing(driver: WebDriver, shop: Shop) -> None:
    profile = demo_profile(shop.url)
    profile.fields["rating"] = Field("p.нет-такого", attribute="data-rating", optional=True)
    items = collect(driver, profile, pause=0, sleep=lambda _: None)
    assert all(item.rating is None for item in items)


def test_missing_cards_report_what_browser_saw(driver: WebDriver, shop: Shop, tmp_path: Path) -> None:
    profile = replace(demo_profile(shop.url), card="div.нет-таких-карточек")
    evidence = tmp_path / "следы"
    with pytest.raises(CollectError, match="не появилось"):
        collect(driver, profile, pause=0, wait=2, sleep=lambda _: None, evidence=evidence)
    assert sorted(path.suffix for path in evidence.iterdir()) == [".html", ".png"]


def test_required_field_missing_is_an_error(driver: WebDriver, shop: Shop) -> None:
    profile = demo_profile(shop.url)
    profile.fields["price"] = Field("p.нет-цены")
    with pytest.raises(CollectError, match="NoSuchElementException"):
        collect(driver, profile, pause=0, sleep=lambda _: None)
