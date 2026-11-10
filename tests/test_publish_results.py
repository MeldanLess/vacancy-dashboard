"""Тесты скрипта, который ведёт от выгрузки до опубликованных чисел.

Скрипт делает три шага: собирает, считает и вписывает раздел в README.
Сеть в тестах не используется — сбор проверяется на подменённой
`collect.collect`, а остальные шаги идут по копии фикстуры.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import publish_results  # noqa: E402

from vacancy_dashboard import collect  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "vacancies_sample.json"


@pytest.fixture()
def рабочее_место(tmp_path: Path) -> dict[str, Path]:
    """Копия фикстуры и README в отдельном каталоге."""
    source = tmp_path / "vacancies.json"
    source.write_bytes(FIXTURE.read_bytes())
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Проект\n\n## Результаты\n\n"
        "<!-- РЕЗУЛЬТАТЫ: НАЧАЛО -->\n\n<!-- РЕЗУЛЬТАТЫ: КОНЕЦ -->\n\n## Дальше\n",
        encoding="utf-8",
    )
    return {
        "source": source,
        "readme": readme,
        "figures": tmp_path / "figures",
        "processed": tmp_path / "processed",
    }


class TestPublishResults:
    """Один запуск — от файла выгрузки до раздела в README."""

    def test_пересчитывает_и_вписывает_раздел(self, рабочее_место: dict[str, Path]) -> None:
        code = publish_results.main(
            [
                "--skip-collect",
                "--input",
                str(рабочее_место["source"]),
                "--figures-dir",
                str(рабочее_место["figures"]),
                "--output-dir",
                str(рабочее_место["processed"]),
                "--readme",
                str(рабочее_место["readme"]),
            ]
        )
        text = рабочее_место["readme"].read_text(encoding="utf-8")
        assert code == 0
        assert "### 1." in text
        assert "## Дальше" in text
        assert (рабочее_место["figures"] / "q1_stack.png").exists()
        assert (рабочее_место["processed"] / "vacancies.csv").exists()

    def test_собирает_и_складывает_выгрузку(
        self, рабочее_место: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        выгрузка = json.loads(FIXTURE.read_text(encoding="utf-8"))
        monkeypatch.setattr(collect, "collect", lambda _settings: выгрузка)

        code = publish_results.main(
            [
                "--input",
                str(рабочее_место["source"]),
                "--figures-dir",
                str(рабочее_место["figures"]),
                "--output-dir",
                str(рабочее_место["processed"]),
                "--readme",
                str(рабочее_место["readme"]),
            ]
        )
        assert code == 0
        assert len(json.loads(рабочее_место["source"].read_text(encoding="utf-8"))) == len(выгрузка)

    def test_пустой_сбор_не_публикуется(
        self, рабочее_место: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(collect, "collect", lambda _settings: [])
        code = publish_results.main(
            [
                "--input",
                str(рабочее_место["source"]),
                "--figures-dir",
                str(рабочее_место["figures"]),
                "--output-dir",
                str(рабочее_место["processed"]),
                "--readme",
                str(рабочее_место["readme"]),
            ]
        )
        assert code == 1
        assert "### 1." not in рабочее_место["readme"].read_text(encoding="utf-8")

    def test_ошибка_сбора_останавливает_работу(
        self, рабочее_место: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def падает(settings: object) -> list[dict]:
            raise collect.CollectError("hh.ru не отвечает")

        monkeypatch.setattr(collect, "collect", падает)
        code = publish_results.main(
            [
                "--input",
                str(рабочее_место["source"]),
                "--figures-dir",
                str(рабочее_место["figures"]),
                "--output-dir",
                str(рабочее_место["processed"]),
                "--readme",
                str(рабочее_место["readme"]),
            ]
        )
        assert code == 1
        assert "### 1." not in рабочее_место["readme"].read_text(encoding="utf-8")

    def test_без_выгрузки_и_без_сбора_выхода_нет(self, tmp_path: Path) -> None:
        code = publish_results.main(
            [
                "--skip-collect",
                "--input",
                str(tmp_path / "нет-такого.json"),
            ]
        )
        assert code == 1
