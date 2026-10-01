"""Браузер для сбора: создаётся на один прогон и закрывается вместе с ним.

Браузер не создаётся при импорте модуля один на всех парсеров (тогда `quit()` одного ронял бы
другой): он живёт внутри контекстного менеджера, а при сбое сохраняет снимок экрана и HTML — чтобы было видно, что он
видел.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.remote.webdriver import WebDriver

BROWSERS = ("edge", "chrome")
WINDOW = (1440, 1000)
PAGE_LOAD_TIMEOUT = 30.0


class BrowserError(RuntimeError):
    pass


def _options(browser: str, headless: bool) -> EdgeOptions | ChromeOptions:
    options: EdgeOptions | ChromeOptions = EdgeOptions() if browser == "edge" else ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument(f"--window-size={WINDOW[0]},{WINDOW[1]}")
    options.add_argument("--log-level=3")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.set_capability("pageLoadStrategy", "eager")  # ждём DOM, а не все картинки
    return options


def make_driver(*, browser: str = "edge", headless: bool = True, timeout: float = PAGE_LOAD_TIMEOUT) -> WebDriver:
    if browser not in BROWSERS:
        raise BrowserError(f"Неизвестный браузер «{browser}»: бывают {', '.join(BROWSERS)}")
    options = _options(browser, headless)
    try:
        driver: WebDriver = (
            webdriver.Edge(options=options)  # type: ignore[arg-type]
            if browser == "edge"
            else webdriver.Chrome(options=options)  # type: ignore[arg-type]
        )
    except WebDriverException as exc:
        raise BrowserError(
            f"Не удалось запустить {browser}: {exc.msg or exc}. Проверьте, что браузер установлен — "
            "драйвер Selenium скачает сам"
        ) from exc
    driver.set_page_load_timeout(timeout)
    return driver


@contextmanager
def browser(*, name: str = "edge", headless: bool = True, timeout: float = PAGE_LOAD_TIMEOUT) -> Iterator[WebDriver]:
    driver = make_driver(browser=name, headless=headless, timeout=timeout)
    try:
        yield driver
    finally:
        driver.quit()


def save_evidence(driver: WebDriver, folder: Path, name: str = "") -> tuple[Path, Path]:
    """Снимок экрана и HTML страницы — чтобы разобраться, почему сбор не удался."""
    folder.mkdir(parents=True, exist_ok=True)
    stamp = name or datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    picture, page = folder / f"{stamp}.png", folder / f"{stamp}.html"
    try:
        driver.save_screenshot(str(picture))
        page.write_text(driver.page_source, encoding="utf-8")
    except WebDriverException:  # браузер мог уже умереть — это не повод терять исходную ошибку
        pass
    return picture, page
