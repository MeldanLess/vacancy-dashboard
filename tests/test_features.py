"""Тесты извлечения признаков из текста вакансии."""

from __future__ import annotations

import pytest

from vacancy_dashboard import config, features


class TestExtractTechnologies:
    """Распознавание стека по свободному тексту."""

    def test_находит_перечисленные_технологии(self) -> None:
        found = features.extract_technologies(
            "Разработчик Python, FastAPI и PostgreSQL, сборка в Docker"
        )
        assert found == ["Docker", "FastAPI", "PostgreSQL", "Python"]

    def test_не_путает_postgresql_с_sql(self) -> None:
        found = features.extract_technologies("PostgreSQL и чистый SQL")
        assert "PostgreSQL" in found
        assert "SQL" in found

    def test_не_находит_sql_внутри_postgresql_по_отдельности(self) -> None:
        # В слове «postgresql» нет границы слова перед «sql», поэтому
        # отдельной технологии «SQL» здесь быть не должно.
        found = features.extract_technologies("Работа с PostgreSQL")
        assert found == ["PostgreSQL"]

    def test_java_и_javascript_различаются(self) -> None:
        found = features.extract_technologies("Java и JavaScript")
        assert found == ["Java", "JavaScript"]

    def test_go_регистрозависим(self) -> None:
        # «Go» — язык, «go» — английский глагол. В требованиях английский
        # глагол встречается чаще, поэтому подмена недопустима.
        assert features.extract_technologies("Go разработчик") == ["Go"]
        assert features.extract_technologies("you need to go to the office") == []

    def test_пустой_текст_даёт_пустой_список(self) -> None:
        assert features.extract_technologies("") == []
        assert features.extract_technologies(None) == []

    def test_результат_отсортирован(self) -> None:
        found = features.extract_technologies("Python, Docker, FastAPI")
        assert found == sorted(found)

    def test_каждая_технология_из_словаря(self) -> None:
        found = features.extract_technologies("Python, Docker, FastAPI, Kafka")
        for name in found:
            assert name in config.TECHNOLOGIES


class TestExtractGrade:
    """Распознавание уровня должности по названию."""

    @pytest.mark.parametrize(
        ("title", "expected"),
        [
            ("Senior Python разработчик", "Senior"),
            ("Middle Backend разработчик", "Middle"),
            ("Junior Python разработчик", "Junior"),
            ("Python разработчик (стажёр)", "Trainee"),
            ("Lead инженер", "Lead"),
            ("Python разработчик", config.GRADE_UNKNOWN),
            ("", config.GRADE_UNKNOWN),
        ],
    )
    def test_уровень_по_названию(self, title: str, expected: str) -> None:
        assert features.extract_grade(title) == expected

    def test_старший_выигрывает_у_младшего(self) -> None:
        # В названии «Senior Middle» встречаются оба уровня: побеждает
        # старший — так устроен порядок правил.
        assert features.extract_grade("Senior Middle разработчик") == "Senior"


class TestNormalizeCity:
    """Группировка городов."""

    @pytest.mark.parametrize(
        ("area", "expected"),
        [
            ("Москва", config.MOSCOW),
            ("Московская область", config.MOSCOW),
            ("Санкт-Петербург", config.SAINT_PETERSBURG),
            ("Ленинградская область", config.SAINT_PETERSBURG),
            ("Казань", config.OTHER_MILLION),
            ("Кострома", config.REGION),
            ("Удалённая работа", config.REMOTE),
            ("", config.REGION),
            (None, config.REGION),
        ],
    )
    def test_город_попадает_в_свою_группу(self, area: str | None, expected: str) -> None:
        assert features.normalize_city(area) == expected


class TestNormalizeWorkFormat:
    """Формат работы по полю `work_format`."""

    def test_удалённый_формат(self) -> None:
        assert features.normalize_work_format(["REMOTE"]) == "Удалённо"

    def test_офис(self) -> None:
        assert features.normalize_work_format(["OFFICE"]) == "Офис"

    def test_гибрид(self) -> None:
        assert features.normalize_work_format(["HYBRID"]) == "Гибрид"

    def test_пустой_список(self) -> None:
        assert features.normalize_work_format([]) == "не указан"
        assert features.normalize_work_format(None) == "не указан"

    def test_при_нескольких_форматах_побеждает_удалённый(self) -> None:
        assert features.normalize_work_format(["OFFICE", "REMOTE"]) == "Удалённо"


class TestNormalizeText:
    """Нормализация текста перед разбором."""

    def test_неразрывный_пробел_заменяется(self) -> None:
        assert features.normalize_text("Docker\u00a0и Python") == "Docker и Python"

    def test_переносы_строк_схлопываются(self) -> None:
        assert features.normalize_text("одна\n\nдве   строки") == "одна две строки"

    def test_пустой_текст(self) -> None:
        assert features.normalize_text(None) == ""

    def test_неразрывный_пробел_лечится(self) -> None:
        # Неразрывный пробел U+00A0 из описаний hh.ru должен превратиться в
        # обычный: иначе слова склеиваются и поиск по тексту ломается.
        source = f"Docker{features.NBSP}и Python"
        assert features.normalize_text(source) == "Docker и Python"
