"""Сборка ноутбуков из кода.

Ноутбуки генерируются скриптом, а не хранятся руками: так код в ноутбуке
не расходится с кодом пайплайна, а в репозитории лежит один источник
правды. Формат `.ipynb` — обычный JSON, поэтому зависимость `nbformat` не
нужна.

Запуск:

    python scripts/build_notebooks.py

Ноутбуки берут настоящую выгрузку, если она есть, и синтетическую фикстуру
иначе — с явным предупреждением. Так ноутбуки запускаются в CI, но рыночные
числа из фикстуры никогда не выдаются за настоящие.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTEBOOKS_DIR = ROOT / "notebooks"

PREAMBLE = '''\
import sys
from pathlib import Path


def find_root() -> Path:
    """Корень репозитория: ищем pyproject.toml вверх по дереву."""
    here = Path.cwd().resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "pyproject.toml").exists():
            return candidate
    return here


ROOT = find_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vacancy_dashboard import analysis, clean, collect  # noqa: E402

RAW = ROOT / "data" / "raw" / "vacancies.json"
FIXTURE = ROOT / "tests" / "fixtures" / "vacancies_sample.json"

source = RAW if RAW.exists() else FIXTURE
print(f"Источник данных: {source}")
if source == FIXTURE:
    print("ВНИМАНИЕ: это синтетическая фикстура, а не рыночные данные. "
          "Числа отсюда нельзя публиковать.")

frame = clean.drop_archived(clean.build_frame(collect.load(source)))
print(f"Вакансий в выборке: {len(frame)}")
frame.head()
'''

STACK_CELLS = [
    (
        "markdown",
        """\
# Какие технологии просят чаще всего

Первый вопрос к данным: какой стек встречается в вакансиях чаще всего и
меняется ли он от месяца к месяцу.

Стек в hh.ru не выделен отдельным полем — его приходится разбирать из
текста требований. Как это сделано и какие у этого способа ограничения —
в [README](../README.md). Здесь только сами числа.""",
    ),
    ("code", PREAMBLE),
    (
        "markdown",
        "## Топ технологий\n\nСчитаются вакансии, а не упоминания: одна вакансия, где "
        "Python назван трижды, попадает в счётчик один раз.",
    ),
    (
        "code",
        """\
result, figure = analysis.question_stack(frame)
print(result.text)
result.table
""",
    ),
    ("code", "figure"),
    (
        "markdown",
        "## Как менялось по месяцам\n\nДоля вакансий с каждой технологией — в процентах "
        "от числа вакансий, опубликованных за месяц.",
    ),
    (
        "code",
        """\
technologies = list(result.table["Технология"][:5])
months = analysis.stack_by_month(frame, technologies)
months.round(1)
""",
    ),
    ("code", "analysis.monthly_trend(frame, technologies)"),
]

GEOGRAPHY_CELLS = [
    (
        "markdown",
        """\
# Где платят больше

Второй вопрос: как предложение по зарплате зависит от города.

Зарплаты приведены к сумме «на руки» (зарплата «до вычета» делится на 1,13),
а «от» — это нижняя граница вилки, а не сама зарплата. Оба ограничения
подписаны на графике.""",
    ),
    ("code", PREAMBLE),
    (
        "code",
        """\
result, figure = analysis.question_geography(frame)
print(result.text)
result.table
""",
    ),
    ("code", "figure"),
    (
        "markdown",
        "## Сколько вакансий без зарплаты\n\nИх нельзя выбрасывать молча: без зарплаты — "
        "не значит «ноль».",
    ),
    (
        "code",
        """\
usable = clean.salary_frame(frame)
print(f"С зарплатой: {len(usable)} из {len(frame)}")
print(f"Без зарплаты: {len(frame) - len(usable)}")
""",
    ),
]

EXPERIENCE_CELLS = [
    (
        "markdown",
        """\
# Сколько стоит опыт

Третий вопрос: что даёт уровень должности и как с ним связана удалённая работа.

Уровень выводится из названия вакансии — hh.ru отдельного поля для него не
держит. Там, где уровень не назван, вакансия остаётся в «не указан», и её
медиана не считается: «не указан» — это не уровень.""",
    ),
    ("code", PREAMBLE),
    (
        "code",
        """\
result, figure = analysis.question_experience(frame)
print(result.text)
result.table
""",
    ),
    ("code", "figure"),
    (
        "markdown",
        "## Доля удалённой работы по уровням\n\nСчитается по всем вакансиям уровня, "
        "в том числе без зарплаты.",
    ),
    (
        "code",
        """\
grouped = frame.groupby("grade")["work_format"].value_counts(normalize=True).unstack(fill_value=0)
grouped
""",
    ),
]

NOTEBOOKS = {
    "01_stack.ipynb": STACK_CELLS,
    "02_geography.ipynb": GEOGRAPHY_CELLS,
    "03_experience.ipynb": EXPERIENCE_CELLS,
}


def markdown_cell(text: str, cell_id: str) -> dict:
    """Ячейка с текстом."""
    return {
        "cell_type": "markdown",
        "id": cell_id,
        "metadata": {},
        "source": text.splitlines(keepends=True),
    }


def code_cell(text: str, cell_id: str) -> dict:
    """Ячейка с кодом."""
    return {
        "cell_type": "code",
        "id": cell_id,
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": text.splitlines(keepends=True),
    }


def build_notebook(cells: list[tuple[str, str]]) -> dict:
    """Собирает ноутбук из ячеек."""
    return {
        "cells": [
            markdown_cell(text, f"cell-{index:02d}")
            if kind == "markdown"
            else code_cell(text, f"cell-{index:02d}")
            for index, (kind, text) in enumerate(cells)
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3.12"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main() -> int:
    """Пишет все ноутбуки в каталог `notebooks/`."""
    NOTEBOOKS_DIR.mkdir(parents=True, exist_ok=True)
    for name, cells in NOTEBOOKS.items():
        target = NOTEBOOKS_DIR / name
        target.write_text(
            json.dumps(build_notebook(cells), ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        print(f"  {name}: {len(cells)} ячеек")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
