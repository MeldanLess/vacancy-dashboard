"""Путь от сырой выгрузки до опубликованных чисел — одной командой.

    python scripts/publish_results.py --text python --pages 20

Что делает скрипт:

1. собирает вакансии с API hh.ru и складывает их в `data/raw/vacancies.json`;
2. прогоняет пайплайн: таблица, три ответа и графики в `docs/figures/`;
3. вписывает раздел «Результаты» в README между маркерами.

Зачем скрипт, если есть `make dump`: `make` есть не везде, а команда,
которая работает везде, где есть Python, — это то, что нужно ночью перед
собеседованием. Содержание шагов у них одно и то же.

Если выгрузка уже собрана и нужно только пересчитать и переписать README:

    python scripts/publish_results.py --skip-collect
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


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
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import render_results  # noqa: E402

from vacancy_dashboard import collect, pipeline  # noqa: E402


def under_root(path: str) -> Path:
    """Путь относительно корня репозитория, если он задан относительным.

    Скрипт должен работать из любого каталога внутри репозитория, а не
    только из корня: путь «data/raw/vacancies.json» тогда означает одно и то
    же и в корне, и в `scripts/`.
    """
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def main(argv: list[str] | None = None) -> int:
    """Точка входа: `python scripts/publish_results.py …`."""
    parser = argparse.ArgumentParser(
        description="Собрать выгрузку, посчитать ответы и вписать раздел в README."
    )
    parser.add_argument("--text", default="python", help="Поисковый запрос.")
    parser.add_argument("--pages", type=int, default=20, help="Сколько страниц запрашивать.")
    parser.add_argument(
        "--input", default="data/raw/vacancies.json", help="Куда складывать сырой JSON."
    )
    parser.add_argument("--figures-dir", default="docs/figures", help="Куда складывать графики.")
    parser.add_argument(
        "--output-dir", default="data/processed", help="Куда складывать обработанную таблицу."
    )
    parser.add_argument("--readme", default="README.md", help="README, который править.")
    parser.add_argument(
        "--skip-collect",
        action="store_true",
        help="Не собирать заново, а посчитать по уже скачанной выгрузке.",
    )
    parser.add_argument(
        "--allow-fixture",
        action="store_true",
        help="Разрешить работу на синтетической фикстуре. Только для тестов.",
    )
    args = parser.parse_args(argv)

    source = under_root(args.input)
    figures_dir = under_root(args.figures_dir)
    output_dir = under_root(args.output_dir)
    readme = under_root(args.readme)
    source.parent.mkdir(parents=True, exist_ok=True)

    if not args.skip_collect:
        print(f"Собираем вакансии: запрос «{args.text}», страниц — {args.pages}…")
        settings = collect.settings_from_env(text=args.text, max_pages=args.pages)
        try:
            vacancies = collect.collect(settings)
        except collect.CollectError as error:
            print(f"Сбор не удался: {error}")
            return 1
        if not vacancies:
            print("Сбор вернул пустой список — публиковать нечего.")
            return 1
        target = collect.save(vacancies, source)
        print(f"Собрано вакансий: {len(vacancies)} → {target}")
    elif not source.exists():
        print(f"Нет файла выгрузки: {source}")
        return 1

    print("Считаем ответы и рисуем графики…")
    pipeline.run(source, output_dir, figures_dir)

    print("Вписываем раздел «Результаты» в README…")
    code = render_results.main(
        [
            "--input",
            str(source),
            "--text",
            args.text,
            "--pages",
            str(args.pages),
            "--figures-dir",
            str(figures_dir),
            "--write-readme",
            str(readme),
            *(["--allow-fixture"] if args.allow_fixture else []),
        ]
    )
    if code != 0:
        return code

    print("\nГотово. Осталось проверить diff и закоммитить:")
    print("  git status --short")
    print("  git add README.md docs/figures")
    print("  git commit -m 'docs: рыночные числа — выгрузка от <дата>'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
