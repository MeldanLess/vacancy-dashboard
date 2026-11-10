"""Тесты очистки: дубликаты, архивные, зарплаты, месяцы."""

from __future__ import annotations

import math

import pandas as pd

from vacancy_dashboard import analysis, clean, config


class TestBuildFrame:
    """Сборка таблицы из ответа API."""

    def test_дубликаты_по_id_отбрасываются(self, sample_vacancies) -> None:
        # В фикстуре одна и та же вакансия встречается дважды: при
        # постраничном сборе hh.ru такое бывает, и в медиане это сдвинуло бы
        # число.
        frame = clean.build_frame(sample_vacancies)
        assert len(frame) == len(frame["id"].unique())
        assert len(frame) == 12

    def test_архивные_убираются(self, sample_vacancies) -> None:
        frame = clean.drop_archived(clean.build_frame(sample_vacancies))
        assert len(frame) == 11
        assert not frame["archived"].any()

    def test_месяц_публикации_считается_по_московскому_времени(self, sample_frame) -> None:
        # Вакансия опубликована 5 октября в 10:00 по Москве — её месяц
        # «2026-10», даже если смотреть в UTC.
        row = sample_frame[sample_frame["id"] == "101"].iloc[0]
        assert row["published_month"] == "2026-10"
        assert row["published_at"].tzinfo is not None

    def test_текст_собирается_из_всех_полей(self, sample_frame) -> None:
        row = sample_frame[sample_frame["id"] == "101"].iloc[0]
        assert "Kafka" in row["text"]
        assert "Docker" in row["text"]


class TestSalary:
    """Приведение зарплат к общему виду."""

    def test_грязная_зарплата_делится_на_ндфл(self, sample_frame) -> None:
        row = sample_frame[sample_frame["id"] == "101"].iloc[0]
        assert bool(row["salary_is_gross"])
        # 250 000 «до вычета» — это 221 239 «на руки».
        assert math.isclose(row["salary_net"], 250000 / 1.13, rel_tol=1e-9)
        assert math.isclose(row["salary_net"], 221238.93805309734, rel_tol=1e-9)

    def test_делить_на_ндфл_по_константе(self) -> None:
        assert clean.NET_DIVISOR == 1.13

    def test_чистая_зарплата_не_меняется(self, sample_frame) -> None:
        row = sample_frame[sample_frame["id"] == "102"].iloc[0]
        assert not bool(row["salary_is_gross"])
        assert row["salary_net"] == 80000

    def test_без_зарплаты_не_ноль(self, sample_frame) -> None:
        row = sample_frame[sample_frame["id"] == "105"].iloc[0]
        assert not bool(row["has_salary"])
        assert pd.isna(row["salary_net"])

    def test_зарплатная_выборка_исключает_пустые(self, sample_frame) -> None:
        usable = clean.salary_frame(sample_frame)
        assert len(usable) == len(sample_frame) - 1
        assert usable["salary_net"].notna().all()


class TestTechnologies:
    """Подсчёт технологий."""

    def test_считаются_вакансии_а_не_упоминания(self, sample_frame) -> None:
        counts = clean.technology_counts(sample_frame)
        # Python есть почти везде, но не в каждой вакансии.
        assert counts["Python"] > 0
        assert counts["Python"] < len(sample_frame)

    def test_порядок_по_убыванию(self, sample_frame) -> None:
        counts = clean.technology_counts(sample_frame)
        assert list(counts.values) == sorted(counts.values, reverse=True)

    def test_матрица_имеет_нули_и_единицы(self, sample_frame) -> None:
        matrix = clean.technology_matrix(sample_frame)
        assert set(matrix.to_numpy().ravel().tolist()) <= {0, 1}
        row = matrix[matrix["Python"] == 1]
        assert len(row) == clean.technology_counts(sample_frame)["Python"]


class TestCityAndFormat:
    """Город и формат работы в таблице."""

    def test_город_сгруппирован(self, sample_frame) -> None:
        row = sample_frame[sample_frame["id"] == "108"].iloc[0]
        assert row["city_group"] == config.REGION

    def test_формат_работы(self, sample_frame) -> None:
        row = sample_frame[sample_frame["id"] == "102"].iloc[0]
        assert row["work_format"] == config.WORK_FORMATS["REMOTE"]

    def test_уровень_определён(self, sample_frame) -> None:
        assert sample_frame[sample_frame["id"] == "101"].iloc[0]["grade"] == "Senior"
        assert sample_frame[sample_frame["id"] == "104"].iloc[0]["grade"] == config.GRADE_UNKNOWN


class TestПустыеДанные:
    """Пустая выборка не должна ронять пайплайн."""

    def test_пустой_список_даёт_пустую_таблицу(self) -> None:
        frame = clean.build_frame([])
        assert frame.empty

    def test_пустая_таблица_без_технологий(self, sample_frame) -> None:
        empty = sample_frame.copy()
        empty["technologies"] = [[] for _ in range(len(empty))]
        matrix = clean.technology_matrix(empty)
        assert matrix.empty

    def test_пустая_выборка_не_ломает_сводку(self) -> None:
        summary = analysis.dataset_summary(clean.build_frame([]))
        assert summary["вакансий"] == 0
        assert summary["период"] == "неизвестно"
