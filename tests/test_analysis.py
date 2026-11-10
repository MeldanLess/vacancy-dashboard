"""Тесты аналитики: тексты ответов, таблицы и сводка."""

from __future__ import annotations

import pandas as pd

from vacancy_dashboard import analysis, clean, config


class TestStack:
    """Первый вопрос: топ технологий."""

    def test_таблица_отсортирована_по_убыванию(self, sample_frame) -> None:
        result, _ = analysis.question_stack(sample_frame)
        counts = list(result.table["Вакансий"])
        assert counts == sorted(counts, reverse=True)

    def test_в_тексте_есть_размер_выборки(self, sample_frame) -> None:
        result, _ = analysis.question_stack(sample_frame)
        assert str(len(sample_frame)) in result.text

    def test_лидер_совпадает_с_таблицей(self, sample_frame) -> None:
        result, _ = analysis.question_stack(sample_frame)
        leader = result.table.iloc[0]
        assert leader["Технология"] in result.text
        assert str(leader["Вакансий"]) in result.text

    def test_пустая_выборка_не_ломает_разбор(self) -> None:
        empty = pd.DataFrame(columns=["id", "technologies"])
        result, _ = analysis.question_stack(empty)
        assert "ни одной технологии" in result.text


class TestGeography:
    """Второй вопрос: зарплаты по группам городов."""

    def test_медиана_совпадает_с_таблицей(self, sample_frame) -> None:
        result, _ = analysis.question_geography(sample_frame)
        moscow = result.table[result.table["Группа"] == config.MOSCOW].iloc[0]
        expected = clean.salary_frame(sample_frame)
        expected = expected[expected["city_group"] == config.MOSCOW]["salary_net"].median()
        assert round(float(moscow["Медиана, ₽"]), -2) == round(float(expected), -2)

    def test_в_тексте_сказано_про_нижние_границы(self, sample_frame) -> None:
        result, _ = analysis.question_geography(sample_frame)
        assert "нижние границы" in result.text
        assert "«от»" in result.text

    def test_малые_группы_помечены(self, sample_frame) -> None:
        result, _ = analysis.question_geography(sample_frame)
        assert str(analysis.MIN_GROUP_SIZE) in result.text

    def test_без_зарплат_не_считается_нулём(self, sample_frame) -> None:
        result, _ = analysis.question_geography(sample_frame)
        assert "Без зарплаты" in result.text
        assert "не считаются нулевыми" in result.text

    def test_пустая_выборка_даёт_пустую_таблицу(self) -> None:
        empty = pd.DataFrame(
            columns=["id", "city_group", "salary_net", "has_salary", "is_russian_salary"]
        )
        result, _ = analysis.question_geography(empty)
        assert result.table.empty
        assert "нет ни одной вакансии" in result.text


class TestExperience:
    """Третий вопрос: уровень должности."""

    def test_уровни_без_вакансий_не_показываются(self, sample_frame) -> None:
        result, _ = analysis.question_experience(sample_frame)
        assert "Lead" not in list(result.table["Уровень"])

    def test_неизвестный_уровень_не_в_таблице(self, sample_frame) -> None:
        result, _ = analysis.question_experience(sample_frame)
        assert config.GRADE_UNKNOWN not in list(result.table["Уровень"])

    def test_в_таблице_есть_общее_число_вакансий(self, sample_frame) -> None:
        result, _ = analysis.question_experience(sample_frame)
        assert "Всего" in result.table.columns
        # Сумма по уровням равна числу вакансий с названным уровнем.
        known = int((sample_frame["grade"] != config.GRADE_UNKNOWN).sum())
        assert int(result.table["Всего"].sum()) == known

    def test_текст_объясняет_неизвестный_уровень(self, sample_frame) -> None:
        result, _ = analysis.question_experience(sample_frame)
        assert "не указан" in result.text

    def test_малые_группы_помечены(self, sample_frame) -> None:
        result, _ = analysis.question_experience(sample_frame)
        assert str(analysis.MIN_GROUP_SIZE) in result.text


class TestSummary:
    """Сводка по выборке."""

    def test_сводка_считается_по_данным(self, sample_frame) -> None:
        summary = analysis.dataset_summary(sample_frame)
        assert summary["вакансий"] == len(sample_frame)
        assert summary["с зарплатой"] == len(clean.salary_frame(sample_frame))
        assert summary["без зарплаты"] == len(sample_frame) - len(clean.salary_frame(sample_frame))
        assert summary["период"] == "2026-10 — 2026-11"


class TestPlural:
    """Склонение числительных."""

    def test_одна_вакансия(self) -> None:
        assert analysis._plural(1, "вакансия", "вакансии", "вакансий") == "вакансия"

    def test_две_вакансии(self) -> None:
        assert analysis._plural(2, "вакансия", "вакансии", "вакансий") == "вакансии"

    def test_пять_вакансий(self) -> None:
        assert analysis._plural(5, "вакансия", "вакансии", "вакансий") == "вакансий"

    def test_одиннадцать_вакансий(self) -> None:
        assert analysis._plural(11, "вакансия", "вакансии", "вакансий") == "вакансий"

    def test_сто_одна_вакансия(self) -> None:
        assert analysis._plural(101, "вакансия", "вакансии", "вакансий") == "вакансия"

    def test_двадцать_одна_вакансия(self) -> None:
        assert analysis._plural(21, "вакансия", "вакансии", "вакансий") == "вакансия"
