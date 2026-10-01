"""Локальная демо-витрина: HTML-магазин и сервер на localhost.

Карточки дорисовываются скриптом с задержкой — как на настоящих витринах. Поэтому демо и тесты
проверяют, что сбор действительно ждёт появления карточек, а не спит фиксированное время.
"""

from __future__ import annotations

import http.server
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path

PAGE_SIZE = 6
DELAY_MS = 300


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    price: int  # копейки
    stock: int | None  # None — нет в наличии
    rating: float


PRODUCTS = (
    Product("KT-01", "Чайник электрический 1,7 л", 249_000, 7, 4.5),
    Product("BL-02", "Блендер погружной 800 Вт", 389_000, 3, 4.2),
    Product("MG-03", "Микроволновая печь 20 л", 799_000, 2, 4.0),
    Product("UT-04", "Утюг с парогенератором", 549_000, 5, 4.6),
    Product("PL-05", "Пылесос вертикальный", 1_299_000, 1, 4.4),
    Product("TS-06", "Тостер на 2 слота", 199_000, 12, 3.9),
    Product("KF-07", "Кофеварка рожковая", 899_000, 4, 4.7),
    Product("MX-08", "Миксер планетарный", 1_099_000, 2, 4.8),
    Product("VS-09", "Весы кухонные электронные", 89_000, 25, 4.1),
    Product("SV-10", "Сушилка для овощей", 459_000, None, 3.7),
    Product("CH-11", "Чайник заварочный стеклянный", 129_000, 9, 4.3),
    Product("TR-12", "Термос 1 л", 159_000, 6, 4.5),
)


def _money(kopecks: int) -> str:
    whole, fraction = divmod(kopecks, 100)
    return f"{whole:,}".replace(",", " ") + f",{fraction:02d} ₽"


def _card(product: Product) -> str:
    stock = f"В наличии: {product.stock} шт." if product.stock else "Нет в наличии"
    css = "stock in-stock" if product.stock else "stock out-of-stock"
    return (
        f'      <article class="product" data-sku="{product.sku}">\n'
        f'        <h3><a href="product-{product.sku}.html" title="{product.name}">{product.name}</a></h3>\n'
        f'        <p class="price">{_money(product.price)}</p>\n'
        f'        <p class="{css}">{stock}</p>\n'
        f'        <p class="rating" data-rating="{product.rating}">рейтинг {product.rating}</p>\n'
        f"      </article>"
    )


def _page(products: Sequence[Product], number: int, pages: int) -> str:
    cards = "\n".join(_card(product) for product in products)
    links = []
    if number > 1:
        links.append(f'<a class="previous" href="{"index" if number == 2 else f"page-{number - 1}"}.html">Назад</a>')
    if number < pages:
        links.append(f'<a class="next" href="page-{number + 1}.html">Следующая страница</a>')
    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>Демо-витрина «Уютный дом» — страница {number} из {pages}</title>
</head>
<body>
  <h1>Уютный дом — бытовая техника</h1>
  <div id="catalog"></div>
  <nav class="pagination">{" ".join(links)}</nav>
  <template id="cards">
{cards}
  </template>
  <script>
    setTimeout(function () {{
      var cards = document.getElementById("cards").content.cloneNode(true);
      document.getElementById("catalog").appendChild(cards);
    }}, {DELAY_MS});
  </script>
</body>
</html>
"""


def write_site(folder: Path, products: Sequence[Product] = PRODUCTS) -> Path:
    """Витрина из статических страниц по PAGE_SIZE карточек. Возвращает папку сайта."""
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.html"):
        old.unlink()
    pages = max(1, -(-len(products) // PAGE_SIZE))
    for number in range(1, pages + 1):
        chunk = products[(number - 1) * PAGE_SIZE : number * PAGE_SIZE]
        name = "index.html" if number == 1 else f"page-{number}.html"
        (folder / name).write_text(_page(chunk, number, pages), encoding="utf-8")
    return folder


def changed(products: Sequence[Product] = PRODUCTS) -> tuple[Product, ...]:
    """Что случилось в магазине между прогонами: цены, наличие, ушедший и новый товар."""
    updated = []
    for product in products:
        if product.sku == "KT-01":
            updated.append(replace(product, price=product.price + 30_000))
        elif product.sku == "BL-02":
            updated.append(replace(product, price=product.price - 45_000))
        elif product.sku == "MG-03":
            updated.append(replace(product, stock=None))
        elif product.sku == "SV-10":
            updated.append(replace(product, stock=4))
        elif product.sku == "TR-12":
            continue  # сняли с витрины
        else:
            updated.append(product)
    updated.append(Product("NW-13", "Соковыжималка шнековая", 899_000, 4, 4.8))
    return tuple(updated)


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass  # без шума в консоли: имя параметра задано стандартной библиотекой


class _QuietServer(http.server.ThreadingHTTPServer):
    def handle_error(self, request: object, client_address: object) -> None:
        pass  # браузер закрывает соединение первым — это не ошибка витрины


@contextmanager
def serve(folder: Path) -> Iterator[str]:
    """Поднимает витрину на свободном порту localhost и отдаёт её адрес."""
    handler = partial(_QuietHandler, directory=str(folder))
    server = _QuietServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
