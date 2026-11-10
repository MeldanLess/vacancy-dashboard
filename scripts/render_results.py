"""Готовит раздел «Результаты» для README из настоящей выгрузки.

Числа в README не пишутся руками: скрипт прогоняет пайплайн по выгрузке и
печатает готовый раздел markdown. Взять оттуда — значит опубликовать то, что
посчитал прогон, а не то, что показалось правдоподобным.

Запуск:

    python scripts/render_results.py --input data/raw/vacancies.json \
        --text python --pages 20

Ключ `--collected-at` задаёт дату среза вручную: по умолчанию берётся время
изменения файла выгрузки. Графики складываются в `docs/figures/` — их тоже
нужно приложить к README.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd


def find_root() -> Path:
    """Корень репозитория: ищем `pyproject.toml` вверх по дереву."""
    here = Path.cwd().resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "pyproject.toml").exists():
            return candidate
    return here


ROOT = find_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vacancy_dashboard import analysis, pipeline  # noqa: E402

MONTHS = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)


def format_date(value: date) -> str:
    """Дата по-русски: «11 ноября 2026»."""
    return f"{value.day} {MONTHS[value.month - 1]} {value.year}"


def format_cell(value: object) -> str:
    """Число в таблице: без лишних нулей, разряды через пробел."""
    if isinstance(value, float):
        if value.is_integer():
            number = int(value)
            if abs(number) >= 1000:
                return f"{number:,}".replace(",", " ")
            return str(number)
        return f"{value:.1f}".replace(".", ",")
    if value is None:
        return "—"
    return str(value)


def markdown_table(frame: pd.DataFrame) -> str:
    """Таблица pandas → markdown без зависимости на `tabulate`."""
    if frame.empty:
        return "_нет данных_"
    header = "| " + " | ".join(str(column) for column in frame.columns) + " |"
    separator = "|" + "|".join("---" for _ in frame.columns) + "|"
    rows = [
        "| " + " | ".join(format_cell(value) for value in row) + " |"
        for row in frame.itertuples(index=False, name=None)
    ]
    return "\n".join([header, separator, *rows])


def summary_table(summary: dict[str, object]) -> str:
    """Сводка по выборке — таблицей из двух колонок."""
    lines = ["| | |", "|---|---|"]
    for key, value in summary.items():
        lines.append(f"| {key} | {format_cell(value)} |")
    return "\n".join(lines)


def build_section(
    summary: dict[str, object],
    results: list[analysis.QuestionResult],
    collected_at: date,
    text: str,
    pages: int,
) -> str:
    """Собирает раздел «Результаты» целиком."""
    parts = [
        "## Результаты",
        "",
        f"_Срез собран {format_date(collected_at)}. Поисковый запрос: `{text}`, "
        f"страниц запрошено: {pages}._",
        "",
        summary_table(summary),
        "",
    ]
    for number, result in enumerate(results, start=1):
        parts += [
            f"### {number}. {result.title}",
            "",
            result.text,
            "",
            markdown_table(result.table),
            "",
            f"![{result.title}](docs/figures/{result.figure_name})",
            "",
        ]
    parts += [
        "---",
        "",
        "**Ограничения, о которых стоит помнить, читая эти числа.** Зарплаты — нижние",
        "границы вилок «от», а не фактические предложения. Группы меньше 30 наблюдений —",
        "шум, а не характеристика рынка: они перечислены в тексте ответа. Признаки «стек»",
        "и «уровень» разобраны из текста, поэтому доля вакансий, где признак удалось",
        "определить, показана рядом с каждым ответом. И это один срез: рынок меняется",
        "между двумя выгрузками, и динамику видно только внутри одной из них.",
        "",
    ]
    return "\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    """Точка входа: `python scripts/render_results.py …`."""
    parser = argparse.ArgumentParser(description="Собрать раздел «Результаты» для README.")
    parser.add_argument(
        "--input", default="data/raw/vacancies.json", help="Файл с сырыми вакансиями."
    )
    parser.add_argument("--text", default="python", help="Поисковый запрос, которым собрано.")
    parser.add_argument("--pages", type=int, default=0, help="Сколько страниц запрашивалось.")
    parser.add_argument(
        "--collected-at",
        default=None,
        help="Дата среза в формате ГГГГ-ММ-ДД. По умолчанию — время файла выгрузки.",
    )
    parser.add_argument("--figures-dir", default="docs/figures", help="Куда сложить графики.")
    parser.add_argument("--output", default=None, help="Файл для записи. Без него — на экран.")
    args = parser.parse_args(argv)

    source = Path(args.input)
    if not source.exists():
        print(f"Нет файла выгрузки: {source}")
        return 1

    frame = pipeline.build(source)
    results = analysis.run_all(frame, Path(args.figures_dir))

    if args.collected_at:
        collected_at = datetime.strptime(args.collected_at, "%Y-%m-%d").date()
    else:
        collected_at = datetime.fromtimestamp(source.stat().st_mtime).date()

    section = build_section(
        analysis.dataset_summary(frame),
        results,
        collected_at,
        args.text,
        args.pages,
    )

    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(section, encoding="utf-8")
        print(f"Раздел записан в {target}")
    else:
        print(section)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
