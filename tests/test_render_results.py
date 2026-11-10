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
