"""Пайплайн: сырой JSON → таблица → три ответа и графики.

Запуск целиком:

    python -m vacancy_dashboard.pipeline --input data/raw/vacancies.json

Что делает пайплайн:

1. читает сырые вакансии, снятые API hh.ru;
2. строит таблицу и убирает архивные;
3. сохраняет обработанную таблицу в `data/processed/vacancies.csv`;
4. отвечает на три вопроса, рисует графики в `docs/figures/`;
5. печатает сводку и тексты ответов — их можно скопировать в README.

Последний пункт — не украшение: цифры в README должны появляться из
выполненного прогона, а не из головы.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from vacancy_dashboard import analysis, clean, collect

# Корень репозитория: на один уровень выше пакета.
ROOT = Path(__file__).resolve().parent.parent

# Синтетическая фикстура для тестов. Её числа — не рыночные.
FIXTURE = ROOT / "tests" / "fixtures" / "vacancies_sample.json"

# Куда кладутся графики, на которые ссылается README.
PUBLISHED_FIGURES = ROOT / "docs" / "figures"


def is_fixture(path: str | Path) -> bool:
    """Файл с синтетической фикстурой?

    `resolve()` не бросает исключений на несуществующем файле, поэтому
    проверка безопасна и для пути, которого ещё нет.
    """
    return Path(path).resolve() == FIXTURE.resolve()


def build(input_path: str | Path) -> pd.DataFrame:
    """Сырой JSON → готовая таблица без архивных вакансий."""
    vacancies = collect.load(input_path)
    frame = clean.build_frame(vacancies)
    return clean.drop_archived(frame)


def save_table(frame: pd.DataFrame, output_dir: Path) -> Path:
    """Сохраняет обработанную таблицу в CSV."""
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "vacancies.csv"
    table = frame.drop(columns=["text"], errors="ignore").copy()
    table["technologies"] = table["technologies"].apply(lambda items: "; ".join(items))
    table.to_csv(target, index=False, encoding="utf-8")
    return target


def run(
    input_path: str | Path,
    output_dir: str | Path = "data/processed",
    figures_dir: str | Path = "docs/figures",
) -> tuple[pd.DataFrame, list[analysis.QuestionResult]]:
    """Прогоняет весь пайплайн и возвращает таблицу и ответы."""
    frame = build(input_path)
    output_path = Path(output_dir)
    figures_path = Path(figures_dir)
    if not frame.empty:
        save_table(frame, output_path)
    results = analysis.run_all(frame, figures_path)
    if not frame.empty:
        analysis.save_trend(frame, figures_path)
    return frame, results


def main(argv: list[str] | None = None) -> int:
    """Точка входа: `python -m vacancy_dashboard.pipeline …`."""
    parser = argparse.ArgumentParser(description="Собрать таблицу и ответы по вакансиям.")
    parser.add_argument(
        "--input",
        default="data/raw/vacancies.json",
        help="Файл с сырыми вакансиями.",
    )
    parser.add_argument("--output-dir", default="data/processed", help="Куда сложить таблицу.")
    parser.add_argument("--figures-dir", default="docs/figures", help="Куда сложить графики.")
    args = parser.parse_args(argv)

    # Графики в `docs/figures/` ссылаются из README: в них должны быть числа
    # настоящей выгрузки. Прогон на фикстуре туда писать нельзя — иначе
    # синтетические числа молча заменят рыночные и попадут в коммит.
    if is_fixture(args.input) and Path(args.figures_dir).resolve() == PUBLISHED_FIGURES:
        print(
            "Отказ: на входе синтетическая фикстура, а графики писались бы в "
            f"{PUBLISHED_FIGURES}. Укажите другой каталог (--figures-dir)."
        )
        return 1

    frame, results = run(args.input, args.output_dir, args.figures_dir)

    summary = analysis.dataset_summary(frame)
    print("=== Выборка ===")
    for key, value in summary.items():
        print(f"{key}: {value}")

    print("\n=== Ответы ===")
    for result in results:
        print(f"\n--- {result.title} ---")
        print(result.text)
        print(result.table.to_string(index=False))

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nСводка: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
