from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest
from selenium.webdriver.remote.webdriver import WebDriver

from shop_monitor import demo
from shop_monitor.browser import BrowserError, make_driver


@dataclass
class Shop:
    """Локальная витрина: адрес и возможность «поменять цены» между прогонами."""

    folder: Path
    url: str

    def update(self, products: Sequence[demo.Product]) -> None:
        demo.write_site(self.folder, products)


@pytest.fixture(scope="session")
def driver() -> Iterator[WebDriver]:
    try:
        instance = make_driver(headless=True)
    except BrowserError as exc:  # на машине без браузера тесты со сбором пропускаются
        pytest.skip(str(exc))
    yield instance
    instance.quit()


@pytest.fixture
def shop(tmp_path: Path) -> Iterator[Shop]:
    folder = demo.write_site(tmp_path / "витрина")
    with demo.serve(folder) as url:
        yield Shop(folder, url)
