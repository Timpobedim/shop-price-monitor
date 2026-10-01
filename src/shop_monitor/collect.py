"""Обход витрины: ждём карточки, собираем поля, переходим на следующую страницу.

Ожидание — явное (WebDriverWait по селектору карточки), а не «поспать полторы секунды»:
страница может отрисоваться и за 200 мс, и за 5 с.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait

from shop_monitor.browser import save_evidence
from shop_monitor.parsing import parse_availability, parse_price, parse_rating
from shop_monitor.profiles import Field, Profile

MAX_PAGES = 3
PAUSE = 1.0
WAIT = 15.0
Sleep = Callable[[float], None]


class CollectError(RuntimeError):
    pass


@dataclass(frozen=True)
class Item:
    key: str  # ссылка или название — по нему товар узнаётся в следующем прогоне
    name: str
    price: int | None  # в копейках, центах, пенсах — в минимальных единицах валюты
    currency: str
    available: bool | None
    quantity: int | None
    rating: float | None
    url: str
    position: int
    page: int


def _text(card: WebElement, field: Field) -> str | None:
    try:
        element = card.find_element(By.CSS_SELECTOR, field.selector)
    except NoSuchElementException:
        if field.optional:
            return None
        raise
    if field.attribute is None:
        return element.text.strip()
    return (element.get_attribute(field.attribute) or "").strip()


def _item(card: WebElement, profile: Profile, position: int, page: int) -> Item:
    values = {name: _text(card, field) for name, field in profile.fields.items()}
    name = (values.get("name") or "").strip()
    price, currency = parse_price(values.get("price") or "")
    available, quantity = parse_availability(values.get("availability") or "")
    url = values.get("link") or ""
    return Item(
        key=url or name,
        name=name,
        price=price,
        currency=currency,
        available=available,
        quantity=quantity,
        rating=parse_rating(values.get("rating") or ""),
        url=url,
        position=position,
        page=page,
    )


def _cards(driver: WebDriver, profile: Profile, wait: float) -> list[WebElement]:
    try:
        WebDriverWait(driver, wait).until(
            expected_conditions.presence_of_element_located((By.CSS_SELECTOR, profile.ready_selector))
        )
    except TimeoutException as exc:
        raise CollectError(
            f"За {wait:.0f} с на странице {driver.current_url} не появилось «{profile.ready_selector}». "
            "Похоже, витрина изменилась или страница не загрузилась"
        ) from exc
    return driver.find_elements(By.CSS_SELECTOR, profile.card)


def _next_url(driver: WebDriver, profile: Profile) -> str | None:
    if not profile.next_page:
        return None
    try:
        link = driver.find_element(By.CSS_SELECTOR, profile.next_page)
    except NoSuchElementException:
        return None  # последняя страница
    return (link.get_attribute("href") or "").strip() or None


def collect(
    driver: WebDriver,
    profile: Profile,
    *,
    max_pages: int = MAX_PAGES,
    pause: float = PAUSE,
    wait: float = WAIT,
    sleep: Sleep = time.sleep,
    evidence: Path | None = None,
) -> list[Item]:
    """Товары витрины по порядку. Ошибка сбора — CollectError, а не пустой список."""
    items: list[Item] = []
    seen_urls: set[str] = set()
    url: str | None = profile.url
    for page in range(1, max_pages + 1):
        if url is None or url in seen_urls:
            break
        seen_urls.add(url)
        if page > 1:
            sleep(pause)  # между страницами — пауза, чтобы не долбить магазин
        try:
            driver.get(url)
            cards = _cards(driver, profile, wait)
            for card in cards:
                items.append(_item(card, profile, position=len(items) + 1, page=page))
            url = _next_url(driver, profile)
        except CollectError:
            if evidence is not None:
                save_evidence(driver, evidence, f"страница-{page}")
            raise
        except (WebDriverException, NoSuchElementException) as exc:
            if evidence is not None:
                save_evidence(driver, evidence, f"страница-{page}")
            raise CollectError(f"Страница {page} ({url}): {exc.__class__.__name__} — {exc}") from exc
    if not items:
        raise CollectError(f"На {profile.url} не нашлось ни одной карточки «{profile.card}»")
    return items
