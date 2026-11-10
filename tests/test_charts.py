"""Тесты оформления графиков.

Проверяются не сами числа (они проверяются в `test_analysis.py`), а правила
оформления: одна ось, одна серия — один цвет, подписи не наезжают друг на
друга.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
import pytest

from vacancy_dashboard import charts


class TestFormatting:
    """Числа в русской записи."""

    def test_деньги_разделяются_пробелом(self) -> None:
        assert charts.money(150000) == "150 000 ₽"

    def test_процент_с_запятой(self) -> None:
        assert charts.percent(63.63) == "63,6 %"


class TestStackChart:
    """Топ технологий."""

    def test_одна_серия_одним_цветом(self, sample_frame) -> None:
        from vacancy_dashboard import analysis

        result, _ = analysis.question_stack(sample_frame)
        figure = charts.stack_chart(result.table, len(sample_frame))
        axes = figure.axes[0]
        colors = {bar.get_facecolor() for bar in axes.patches}
        assert len(colors) == 1
        plt.close(figure)

    def test_подписи_только_у_лидеров(self, sample_frame) -> None:
        from vacancy_dashboard import analysis

        result, _ = analysis.question_stack(sample_frame)
        figure = charts.stack_chart(result.table, len(sample_frame))
        labels = [text.get_text() for text in figure.axes[0].texts]
        assert len(labels) <= charts.LABELLED_BARS
        plt.close(figure)

    def test_пустая_таблица_не_ломает_график(self) -> None:
        empty = pd.DataFrame(columns=["Технология", "Вакансий", "Доля, %"])
        figure = charts.stack_chart(empty, 0)
        assert figure.axes[0].texts
        plt.close(figure)


class TestExperienceChart:
    """Две меры по уровню должности."""

    def test_две_отдельные_оси_вместо_двух_шкал(self, sample_frame) -> None:
        from vacancy_dashboard import analysis

        result, _ = analysis.question_experience(sample_frame)
        figure = charts.experience_chart(result.table, 10)
        # Две панели — и ни одной «второй шкалы Y» на одной панели.
        assert len(figure.axes) == 2
        for axes in figure.axes:
            assert len(axes.get_shared_y_axes().get_siblings(axes)) == 1
        plt.close(figure)


class TestMonthlyTrend:
    """Динамика по месяцам."""

    def test_подписи_не_слипаются(self) -> None:
        # Две технологии с одинаковой долей в конце: подписи не должны
        # наложиться друг на друга.
        months = pd.DataFrame(
            {
                "Месяц": ["2026-10", "2026-11"],
                "Вакансий": [10, 10],
                "Python": [50.0, 50.0],
                "Docker": [20.0, 50.0],
            }
        )
        figure = charts.monthly_trend_chart(months, ["Python", "Docker"])
        axes = figure.axes[0]
        positions = [text.get_position()[1] for text in axes.texts]
        assert len(positions) == 2
        assert abs(positions[0] - positions[1]) > 1.0
        plt.close(figure)

    def test_пустые_данные_не_ломают_график(self) -> None:
        empty = pd.DataFrame(columns=["Месяц", "Вакансий"])
        figure = charts.monthly_trend_chart(empty, ["Python"])
        assert figure.axes[0].texts
        plt.close(figure)


@pytest.fixture(autouse=True)
def _закрываем_графики():
    """Все графики закрываются, иначе они копятся в памяти тестов."""
    yield
    plt.close("all")
