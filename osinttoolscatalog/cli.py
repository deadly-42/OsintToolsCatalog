from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table

from osinttoolscatalog import __version__
from osinttoolscatalog.catalog import BOT_BLOCK, DEAD, ERROR, OK, check_links, get_category, load_catalog
from osinttoolscatalog.checker import FOUND, NOT_FOUND, SKIPPED, UNCLEAR, check_username
from osinttoolscatalog.sources import load_sources

console = Console()
_BAD_CHARS = re.compile(r"[\s/\\?#%<>\"']")


def _fix_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _progress(label: str, total: int) -> tuple[Progress, int]:
    progress = Progress(TextColumn("[progress.description]{task.description}"), BarColumn(),
                        TaskProgressColumn(), console=console, transient=True)
    return progress, progress.add_task(label, total=total)


# ───────────────────────── каталог ─────────────────────────

def show_category(category_id: int) -> bool:
    cat = get_category(category_id)
    if cat is None:
        console.print("[red]Такой категории нет.[/red]")
        return False
    table = Table(title=f"{cat['id']}. {cat['title']} — {len(cat['tools'])} инструментов", show_lines=False)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Инструмент", style="bold cyan")
    table.add_column("Ссылка", overflow="fold")
    table.add_column("Описание", overflow="fold")
    for i, tool in enumerate(cat["tools"], 1):
        table.add_row(str(i), tool["name"], tool["url"], tool["desc"])
    console.print(table)
    console.print(f"[dim]{cat['description']}[/dim]")
    return True


def cmd_check_links(category_id: int | None, concurrency: int, timeout: float) -> None:
    tools = []
    for cat in load_catalog():
        if category_id in (None, cat["id"]):
            tools += [dict(t, category_id=cat["id"]) for t in cat["tools"]]
    console.print(f"Проверяю ссылки каталога: {len(tools)}")
    progress, task = _progress("Проверка ссылок", len(tools))
    with progress:
        results = check_links(tools, timeout=timeout, concurrency=concurrency,
                              on_result=lambda _r: progress.advance(task))
    count = lambda s: sum(r["status"] == s for r in results)
    bad = [r for r in results if r["status"] in (DEAD, ERROR)]
    if bad:
        table = Table(title="Проблемные ссылки")
        table.add_column("Кат.", justify="right")
        table.add_column("Инструмент", style="red")
        table.add_column("HTTP / ошибка")
        table.add_column("Ссылка", overflow="fold")
        for r in bad:
            table.add_row(str(r["category"]), r["name"], str(r["http_status"] or r.get("error", "—")), r["url"])
        console.print(table)
    console.print(f"[green]Работают: {count(OK)}[/green]  [yellow]Закрыты защитой от ботов (скорее всего живы): "
                  f"{count(BOT_BLOCK)}[/yellow]  [red]Не работают/ошибка: {count(DEAD) + count(ERROR)}[/red]")


# ───────────────────────── мини-поиск по нику ─────────────────────────

def clean_username(raw: str) -> str | None:
    name = raw.strip().lstrip("@")
    if not name or len(name) > 64 or _BAD_CHARS.search(name):
        return None
    return name


def username_search(name: str, *, timeout: float = 8.0, concurrency: int = 30, details: bool = False,
                    show_all: bool = False, output: Path | None = None, verify: bool = True) -> None:
    items = load_sources()
    console.print(Panel.fit(
        f"[bold]Поиск публичного ника:[/bold] [cyan]{name}[/cyan]  [dim]({len(items)} источников)[/dim]\n"
        "[dim]Проверяются только открытые страницы; возможны ложные совпадения.[/dim]",
        title="Мини-поиск", border_style="blue"))

    progress, task = _progress("Проверка", len(items))
    with progress:
        results = check_username(name, sources=items, timeout=timeout, concurrency=concurrency,
                                 verify=verify, details=details, on_result=lambda _r: progress.advance(task))

    checked = [r for r in results if r["status"] != SKIPPED]
    if checked and all("error" in r for r in checked):
        console.print("[bold red]Ни один сайт не ответил.[/bold red] Проверьте интернет, VPN или прокси.")
        return

    table = Table(title="Результаты")
    table.add_column("Статус", width=10)
    table.add_column("Источник", style="cyan")
    table.add_column("Ссылка", overflow="fold")
    if details:
        table.add_column("Метаданные профиля", overflow="fold")
    for r in results:
        if r["status"] != FOUND and not show_all:
            continue
        style = {FOUND: "green", UNCLEAR: "yellow"}.get(r["status"], "dim")
        row = [f"[{style}]{r['status']}[/{style}]", r["name"], r["url"]]
        if details:
            p = r.get("profile", {})
            row.append(" | ".join(v for v in (p.get("title"), p.get("description")) if v))
        table.add_row(*row)
    console.print(table)

    count = lambda s: sum(r["status"] == s for r in results)
    found, missing, unclear, skipped = count(FOUND), count(NOT_FOUND), count(UNCLEAR), count(SKIPPED)
    console.print(Panel.fit(
        f"[bold]Итог по нику[/bold] [cyan]{name}[/cyan]\n"
        f"Проверено источников: [bold]{len(checked)}[/bold]\n"
        f"[green]Аккаунт найден: {found}[/green]\n"
        f"[red]Аккаунт не найден: {missing}[/red]\n"
        f"[yellow]Не удалось определить (защита сайта, лимиты, сеть, ненадёжный ответ сайта): {unclear}[/yellow]"
        + (f"\n[dim]Пропущено (ник не подходит формату сайта): {skipped}[/dim]" if skipped else ""),
        border_style="green" if found else "red"))

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({
            "tool": "OsintToolsCatalog", "version": __version__, "query": name,
            "summary": {"checked": len(checked), "found": found, "not_found": missing,
                        "unclear": unclear, "skipped": skipped},
            "results": results,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(f"[green]JSON сохранён:[/green] {output.resolve()}")


# ───────────────────────── меню ─────────────────────────

def run_menu() -> None:
    cats = load_catalog()
    total = sum(len(c["tools"]) for c in cats)
    console.print(Panel.fit(
        f"[bold cyan]OsintToolsCatalog[/bold cyan] [green]{__version__}[/green]\n"
        f"[dim]Каталог OSINT-инструментов: {len(cats)} категорий, {total} инструментов + мини-поиск по нику[/dim]",
        border_style="blue"))

    while True:
        console.print()
        for c in cats:
            console.print(f"[bold]{c['id']:>2}[/bold] — {c['title']} [dim]({len(c['tools'])})[/dim]")
        console.print("[bold] 0[/bold] — выход")
        try:
            choice = Prompt.ask("Введите цифру от 0 до 10",
                                choices=[str(i) for i in range(len(cats) + 1)], show_choices=False)
            if choice == "0":
                console.print("До свидания!")
                return
            show_category(int(choice))
            if choice == "1" and Confirm.ask("Запустить встроенный мини-поиск по нику?", default=True):
                name = clean_username(Prompt.ask("Введите юзернейм"))
                if name is None:
                    console.print("[red]Юзернейм должен быть без пробелов и символов / \\ ? # % (до 64 символов).[/red]")
                else:
                    out = None
                    if Confirm.ask("Сохранить результаты в JSON-файл?", default=False):
                        safe = re.sub(r"[^\w.-]", "_", name)
                        out = Path(f"results_{safe}.json")
                    username_search(name, output=out)
        except (KeyboardInterrupt, EOFError):
            console.print("\nВыход.")
            return
        except Exception as exc:  # одна ошибка не должна закрывать программу
            console.print(f"[red]Ошибка:[/red] {type(exc).__name__}: {exc}")
            console.print("[dim]Возвращаюсь в меню.[/dim]")


# ───────────────────────── argparse ─────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="osintcatalog", description="OsintToolsCatalog — каталог OSINT-инструментов и мини-поиск по нику.")
    sub = p.add_subparsers(dest="command")
    sub.add_parser("version", help="показать версию")

    lp = sub.add_parser("list", help="показать категорию каталога (1–10)")
    lp.add_argument("category", type=int, nargs="?", help="номер категории; без номера — список категорий")

    sp = sub.add_parser("search", help="мини-поиск публичных профилей по нику")
    sp.add_argument("username")
    sp.add_argument("-o", "--output", type=Path, help="сохранить результат в JSON")
    sp.add_argument("--all", action="store_true", dest="show_all", help="показывать и ненайденные")
    sp.add_argument("--details", action="store_true", help="показать публичные og-метаданные найденных профилей")
    sp.add_argument("--no-verify", action="store_true", help="не перепроверять находки контрольным ником")
    sp.add_argument("--timeout", type=float, default=8.0)
    sp.add_argument("--concurrency", type=int, default=30)

    cp = sub.add_parser("check-links", help="проверить, что ссылки каталога живы")
    cp.add_argument("category", type=int, nargs="?")
    cp.add_argument("--timeout", type=float, default=10.0)
    cp.add_argument("--concurrency", type=int, default=20)
    return p


def main(argv: list[str] | None = None) -> None:
    _fix_encoding()
    args = build_parser().parse_args(argv)
    try:
        if args.command is None:
            run_menu()
        elif args.command == "version":
            console.print(f"[bold cyan]OsintToolsCatalog[/bold cyan] [green]{__version__}[/green]")
        elif args.command == "list":
            if args.category is None:
                for c in load_catalog():
                    console.print(f"[bold]{c['id']:>2}[/bold] — {c['title']} [dim]({len(c['tools'])})[/dim]")
            else:
                show_category(args.category)
        elif args.command == "search":
            name = clean_username(args.username)
            if name is None:
                console.print("[red]Юзернейм должен быть без пробелов и символов / \\ ? # % (до 64 символов).[/red]")
                sys.exit(2)
            username_search(name, timeout=args.timeout, concurrency=max(1, min(args.concurrency, 100)),
                            details=args.details, show_all=args.show_all, output=args.output,
                            verify=not args.no_verify)
        elif args.command == "check-links":
            cmd_check_links(args.category, max(1, min(args.concurrency, 100)), args.timeout)
    except KeyboardInterrupt:
        console.print("\nПрервано.")
        sys.exit(130)


if __name__ == "__main__":
    main()
