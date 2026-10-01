"""Командная строка.

shop-monitor run --profile books --max-pages 2 --db история.sqlite -o отчёт.xlsx
shop-monitor demo --out demo
shop-monitor profiles
shop-monitor history --db история.sqlite
"""

from __future__ import annotations

import argparse
import io
import sys
from collections.abc import Sequence
from pathlib import Path
from tempfile import TemporaryDirectory

from shop_monitor import demo as demo_shop
from shop_monitor.browser import BrowserError, browser
from shop_monitor.collect import CollectError, Item, collect
from shop_monitor.compare import Change, compare, moved
from shop_monitor.profiles import BUILTIN, Profile, ProfileError, demo_profile, resolve, to_json
from shop_monitor.report import ReportError, print_report, write_report
from shop_monitor.storage import connect, items_of, now, previous_run, runs, save_run


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="shop-monitor", description="Монитор цен и наличия в интернет-магазине")
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="собрать витрину и сравнить с прошлым прогоном")
    run.add_argument("--profile", default="books", help="имя встроенного профиля или путь к JSON-файлу")
    run.add_argument("--db", type=Path, default=Path("монитор.sqlite"), help="файл истории прогонов")
    run.add_argument("-o", "--out", type=Path, help="сохранить отчёт в .xlsx")
    run.add_argument("--max-pages", type=int, default=3, help="сколько страниц витрины обойти")
    run.add_argument("--pause", type=float, default=1.0, help="пауза между страницами, с")
    run.add_argument("--browser", choices=("edge", "chrome"), default="edge")
    run.add_argument("--no-headless", action="store_true", help="показать окно браузера")
    run.add_argument("--evidence", type=Path, default=Path("следы"), help="куда класть снимок экрана при сбое")

    sample = commands.add_parser("demo", help="локальная витрина: два прогона и отчёт об изменениях")
    sample.add_argument("--out", type=Path, default=Path("demo"), help="папка для витрины, базы и отчёта")
    sample.add_argument("--browser", choices=("edge", "chrome"), default="edge")
    sample.add_argument("--no-headless", action="store_true", help="показать окно браузера")

    commands.add_parser("profiles", help="показать встроенные профили и пример своего")

    history = commands.add_parser("history", help="последние прогоны из базы")
    history.add_argument("--db", type=Path, default=Path("монитор.sqlite"))
    history.add_argument("--profile", help="только этот профиль")
    return parser


def _collect_once(
    profile: Profile, args: argparse.Namespace, database: Path, *, pause: float, max_pages: int
) -> tuple[list[Item], list[Change], list[Item]]:
    started = now()
    with browser(name=args.browser, headless=not args.no_headless) as driver:
        items = collect(
            driver,
            profile,
            max_pages=max_pages,
            pause=pause,
            evidence=getattr(args, "evidence", None),
        )
    with connect(database) as connection:
        run_id = save_run(connection, profile.name, profile.url, items, started, now())
        previous = previous_run(connection, profile.name, run_id)
        before = items_of(connection, previous.id) if previous else []
    return items, compare(before, items), before


def _run(args: argparse.Namespace) -> int:
    profile = resolve(args.profile)
    items, changes, before = _collect_once(profile, args, args.db, pause=args.pause, max_pages=args.max_pages)
    print_report(profile, items, changes, first_run=not before)
    if args.out:
        with connect(args.db) as connection:
            history = runs(connection, profile.name, limit=10)
        write_report(args.out, items, changes, history, moved(before, items))
        print(f"\nОтчёт: {args.out}")
    return 0


def _demo(args: argparse.Namespace) -> int:
    folder = args.out
    site = folder / "витрина"
    demo_shop.write_site(site)
    database = folder / "монитор.sqlite"
    database.unlink(missing_ok=True)
    report = folder / "отчёт.xlsx"
    with demo_shop.serve(site) as base_url:
        profile = demo_profile(base_url)
        print("Прогон 1 — как есть")
        first, _, _ = _collect_once(profile, args, database, pause=0.2, max_pages=3)
        print(f"  собрано товаров: {len(first)}")
        demo_shop.write_site(site, demo_shop.changed())
        print("\nПрогон 2 — в магазине изменились цены и наличие")
        items, changes, before = _collect_once(profile, args, database, pause=0.2, max_pages=3)
        print_report(profile, items, changes, first_run=False)
        with connect(database) as connection:
            history = runs(connection, profile.name, limit=10)
        write_report(report, items, changes, history, moved(before, items))
    print(f"\nОтчёт: {report}\nВитрина: {site}\nИстория: {database}")
    return 0


def _profiles() -> int:
    print("Встроенные профили:")
    for name, profile in BUILTIN.items():
        print(f"  {name} — {profile.title or profile.url}")
    print("\nСвой магазин описывается таким JSON-файлом (передайте путь в --profile):\n")
    with TemporaryDirectory() as folder:
        print(to_json(demo_profile(f"file:///{folder}")))
    return 0


def _history(args: argparse.Namespace) -> int:
    with connect(args.db) as connection:
        history = runs(connection, args.profile, limit=20)
    if not history:
        print("В базе пока нет прогонов")
        return 0
    print(f"{'Прогон':>7}  {'Профиль':<16} {'Начат':<17} {'Товаров':>8} {'Страниц':>8}")
    for run in history:
        started = run.started.astimezone().strftime("%d.%m.%Y %H:%M")
        print(f"{run.id:>7}  {run.profile:<16} {started:<17} {run.items:>8} {run.pages:>8}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(errors="replace")
    args = _parser().parse_args(argv)
    try:
        if args.command == "run":
            return _run(args)
        if args.command == "demo":
            return _demo(args)
        if args.command == "profiles":
            return _profiles()
        return _history(args)
    except (ProfileError, BrowserError) as exc:
        print(exc, file=sys.stderr)
        return 2
    except (CollectError, ReportError) as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
