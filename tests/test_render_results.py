"""Тесты скрипта, который готовит раздел «Результаты» для README.

Скрипт печатает числа, которые потом попадут в README, поэтому он должен
выводить их одинаково при любом запуске: никаких округлений на глаз и никаких
значений, которых не было в прогоне.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import render_results  # noqa: E402

from vacancy_dashboard import analysis  # noqa: E402


class TestFormatting:
    """Форматирование чисел и дат."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (194700.0, "194 700"),
            (63.6, "63,6"),
            (50.0, "50"),
            (None, "—"),
            ("Текст", "Текст"),
        ],
    )
    def test_число_пишется_по_русски(self, value: object, expected: str) -> None:
        assert render_results.format_cell(value) == expected

    def test_дата_по_русски(self) -> None:
        assert render_results.format_date(date(2026, 11, 10)) == "10 ноября 2026"


class TestMarkdownTable:
    """Таблица превращается в markdown."""

    def test_заголовок_и_разделитель(self) -> None:
        table = pd.DataFrame({"Технология": ["Python"], "Вакансий": [7]})
        rendered = render_results.markdown_table(table)
        assert "| Технология | Вакансий |" in rendered
        assert "|---|---|" in rendered
        assert "| Python | 7 |" in rendered

    def test_пустая_таблица(self) -> None:
        empty = pd.DataFrame(columns=["Технология", "Вакансий"])
        assert render_results.markdown_table(empty) == "_нет данных_"


class TestSection:
    """Раздел собирается из ответов прогона."""

    def test_в_разделе_есть_ответы_и_графики(self, sample_frame, tmp_path: Path) -> None:
        results = analysis.run_all(sample_frame, tmp_path)
        section = render_results.build_section(
            analysis.dataset_summary(sample_frame),
            results,
            date(2026, 11, 10),
            "python",
            20,
        )
        assert "## Результаты" in section
        assert "### 1." in section
        assert "### 3." in section
        assert "docs/figures/q1_stack.png" in section
        assert "10 ноября 2026" in section

    def test_текст_ответа_попадает_в_раздел(self, sample_frame, tmp_path: Path) -> None:
        results = analysis.run_all(sample_frame, tmp_path)
        section = render_results.build_section(
            analysis.dataset_summary(sample_frame),
            results,
            date(2026, 11, 10),
            "python",
            20,
        )
        assert results[0].text in section
        assert "нижние границы вилок" in section


class TestWriteIntoReadme:
    """Раздел вписывается в README сам, а не копируется руками."""

    def test_тело_пишется_между_маркерами(self) -> None:
        readme = (
            "# Проект\n\n## Результаты\n\n"
            f"{render_results.MARKER_START}\n\nстарое\n\n{render_results.MARKER_END}\n\n"
            "## Дальше\n"
        )
        updated = render_results.replace_section(readme, "новое")
        assert "новое" in updated
        assert "старое" not in updated
        assert "## Дальше" in updated

    def test_без_маркеров_это_ошибка(self) -> None:
        with pytest.raises(ValueError, match="маркер"):
            render_results.replace_section("# Проект\n\n## Результаты\n", "новое")

    def test_фикстура_опознаётся(self) -> None:
        assert render_results.is_fixture(render_results.FIXTURE)
        assert not render_results.is_fixture(ROOT / "data" / "raw" / "vacancies.json")

    def test_на_фикстуре_в_readme_не_пишется(self, tmp_path: Path, capsys) -> None:
        readme = tmp_path / "README.md"
        readme.write_text(
            f"{render_results.MARKER_START}\n\n{render_results.MARKER_END}\n", encoding="utf-8"
        )
        code = render_results.main(
            [
                "--input",
                str(render_results.FIXTURE),
                "--write-readme",
                str(readme),
                "--figures-dir",
                str(tmp_path / "figures"),
            ]
        )
        assert code == 1
        assert "новое" not in readme.read_text(encoding="utf-8")
        assert "Отказ" in capsys.readouterr().out

    def test_выгрузка_пишется_в_readme(self, tmp_path: Path) -> None:
        # Копия фикстуры в другой путь — обычная выгрузка для скрипта.
        source = tmp_path / "vacancies.json"
        source.write_bytes(render_results.FIXTURE.read_bytes())
        readme = tmp_path / "README.md"
        readme.write_text(
            f"# Проект\n\n## Результаты\n\n{render_results.MARKER_START}\n\n"
            f"{render_results.MARKER_END}\n\n## Дальше\n",
            encoding="utf-8",
        )
        code = render_results.main(
            [
                "--input",
                str(source),
                "--write-readme",
                str(readme),
                "--figures-dir",
                str(tmp_path / "figures"),
                "--text",
                "python",
                "--pages",
                "20",
                "--collected-at",
                "2026-11-10",
            ]
        )
        updated = readme.read_text(encoding="utf-8")
        assert code == 0
        assert "### 1." in updated
        assert "10 ноября 2026" in updated
        assert "## Дальше" in updated
        # Заголовок не должен задваиваться.
        assert updated.count("## Результаты") == 1
