"""Готовит раздел «Результаты» для README из настоящей выгрузки.

Числа в README не пишутся руками: скрипт прогоняет пайплайн по выгрузке и
печатает готовый раздел markdown. Взять оттуда — значит опубликовать то, что
посчитал прогон, а не то, что показалось правдоподобным.

Запуск:

    python scripts/render_results.py --input data/raw/vacancies.json \
        --text python --pages 20

С ключом `--write-readme README.md` скрипт не печатает раздел, а вписывает его
между маркерами `<!-- РЕЗУЛЬТАТЫ: НАЧАЛО -->` и `<!-- РЕЗУЛЬТАТЫ: КОНЕЦ -->`:
тогда опубликованные числа и есть числа прогона, а не переписанные руками.

Ключ `--collected-at` задаёт дату среза вручную: по умолчанию берётся время
изменения файла выгрузки. Графики складываются в `docs/figures/` — их тоже
нужно приложить к README.

Синтетическая фикстура в README не попадёт: на ней скрипт откажется работать
без явного `--allow-fixture`.
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


def build_body(
    summary: dict[str, object],
    results: list[analysis.QuestionResult],
    collected_at: date,
    text: str,
    pages: int,
) -> str:
    """Тело раздела «Результаты» — без заголовка.

    Заголовок живёт в README уже на месте, а скрипт вписывает между маркерами
    только тело: иначе при каждом прогоне в README появлялся бы второй
    заголовок «Результаты».
    """
    parts = [
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


def build_section(
    summary: dict[str, object],
    results: list[analysis.QuestionResult],
    collected_at: date,
    text: str,
    pages: int,
) -> str:
    """Собирает раздел «Результаты» целиком — с заголовком."""
    return "\n".join(["## Результаты", "", build_body(summary, results, collected_at, text, pages)])


# Маркеры, между которыми в README живёт автоматический раздел.
MARKER_START = "<!-- РЕЗУЛЬТАТЫ: НАЧАЛО -->"
MARKER_END = "<!-- РЕЗУЛЬТАТЫ: КОНЕЦ -->"

# Синтетическая фикстура: её числа нельзя публиковать как рыночные.
# Путь и проверка живут в пайплайне — там же, где строится таблица.
FIXTURE = pipeline.FIXTURE
is_fixture = pipeline.is_fixture


def replace_section(readme_text: str, body: str) -> str:
    """Вписывает тело раздела между маркерами в текст README.

    Всё, что вне маркеров, остаётся как было: скрипт меняет только числа
    результатов, а не руками переписанные объяснения.
    """
    start = readme_text.find(MARKER_START)
    end = readme_text.find(MARKER_END)
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"В README нет маркеров {MARKER_START} … {MARKER_END}")
    head = readme_text[: start + len(MARKER_START)]
    tail = readme_text[end:]
    return f"{head}\n\n{body}\n\n{tail}"


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
    parser.add_argument(
        "--write-readme",
        default=None,
        help="README, в который вписать раздел между маркерами.",
    )
    parser.add_argument(
        "--allow-fixture",
        action="store_true",
        help="Разрешить вписать в README данные синтетической фикстуры. Только для тестов.",
    )
    args = parser.parse_args(argv)

    source = Path(args.input)
    if not source.exists():
        print(f"Нет файла выгрузки: {source}")
        return 1

    if is_fixture(source) and not args.allow_fixture:
        print(
            "Отказ: на входе синтетическая фикстура. Её числа нельзя публиковать "
            "как рыночные — соберите настоящую выгрузку."
        )
        return 1

    frame = pipeline.build(source)
    results = analysis.run_all(frame, Path(args.figures_dir))

    if args.collected_at:
        collected_at = datetime.strptime(args.collected_at, "%Y-%m-%d").date()
    else:
        collected_at = datetime.fromtimestamp(source.stat().st_mtime).date()

    summary = analysis.dataset_summary(frame)
    section = build_section(summary, results, collected_at, args.text, args.pages)

    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(section, encoding="utf-8", newline="\n")
        print(f"Раздел записан в {target}")
    else:
        print(section)

    if args.write_readme:
        readme_path = Path(args.write_readme)
        readme_text = readme_path.read_text(encoding="utf-8")
        body = build_body(summary, results, collected_at, args.text, args.pages)
        readme_path.write_text(replace_section(readme_text, body), encoding="utf-8", newline="\n")
        print(f"Раздел вписан в {readme_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
