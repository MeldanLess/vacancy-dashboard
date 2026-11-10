"""Тесты отрисовки дашборда.

Страница проверяется не «на глаз», а через `streamlit.testing`: скрипт
запускается как настоящая страница, и тест смотрит на то, что на ней
появилось. Ошибка в приложении падает в CI, а не на экране у человека.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_PATH = ROOT / "app" / "dashboard.py"
FIXTURE = ROOT / "tests" / "fixtures" / "vacancies_sample.json"

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest  # noqa: E402

from vacancy_dashboard import config  # noqa: E402


@pytest.fixture()
def page(monkeypatch: pytest.MonkeyPatch) -> AppTest:
    """Страница дашборда на синтетической фикстуре.

    Путь к данным задаётся переменной окружения: тест не должен зависеть от
    того, лежит ли рядом настоящая выгрузка.
    """
    monkeypatch.setenv("VACANCY_DASHBOARD_DATA", str(FIXTURE))
    app = AppTest.from_file(str(APP_PATH), default_timeout=60)
    app.run()
    return app


def _filtered_count(page: AppTest) -> int:
    """Число вакансий после фильтров — из подписи в боковой панели."""
    captions = [caption.value for caption in page.sidebar.caption]
    for caption in captions:
        match = re.search(r"После фильтров: (\d+)", caption)
        if match:
            return int(match.group(1))
    raise AssertionError(f"Подписи с числом фильтра нет: {captions}")


class TestPage:
    """Страница открывается и показывает данные."""

    def test_страница_отрисовывается_без_ошибок(self, page: AppTest) -> None:
        assert not page.exception

    def test_предупреждение_о_синтетической_фикстуре(self, page: AppTest) -> None:
        assert page.warning
        assert "фикстур" in page.warning[0].value

    def test_метрики_выборки(self, page: AppTest) -> None:
        values = {metric.label: metric.value for metric in page.metric}
        assert values["Вакансий"] == "11"
        assert values["С зарплатой"] == "10"
        assert values["Городов"] == "7"
        assert values["Технологий"] == "30"

    def test_три_ответа_на_странице(self, page: AppTest) -> None:
        titles = [header.value for header in page.subheader]
        assert "Какие технологии просят чаще всего" in titles
        assert "Где платят больше" in titles
        assert "Сколько стоит опыт" in titles


class TestFilters:
    """Фильтры меняют выборку."""

    def test_без_фильтров_выборка_вся(self, page: AppTest) -> None:
        # Вакансии без названного уровня должности тоже остаются в выборке:
        # иначе счётчик «Вакансий» вверху и ответы считались бы по разным
        # данным.
        assert _filtered_count(page) == 11

    def test_только_с_зарплатой(self, page: AppTest) -> None:
        page.sidebar.checkbox[0].check().run()
        assert not page.exception
        assert _filtered_count(page) == 10

    def test_один_город(self, page: AppTest) -> None:
        page.sidebar.multiselect[0].set_value(["Москва"]).run()
        assert not page.exception
        assert 0 < _filtered_count(page) < 11

    def test_фильтр_по_уровню_видит_и_не_указан(self, page: AppTest) -> None:
        page.sidebar.multiselect[1].set_value([config.GRADE_UNKNOWN]).run()
        assert not page.exception
        assert _filtered_count(page) == 6
