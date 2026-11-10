"""Тесты дашборда: модуль должен собираться и считать данные.

Streamlit ставится вместе с остальными зависимостями, но если его нет —
тест пропускается, а не падает: без него приложение всё равно не запустится.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

APP_PATH = Path(__file__).resolve().parent.parent / "app" / "dashboard.py"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "vacancies_sample.json"


@pytest.fixture(scope="module")
def dashboard():
    """Загруженный модуль дашборда."""
    pytest.importorskip("streamlit")
    spec = importlib.util.spec_from_file_location("dashboard", APP_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestDashboard:
    """Модуль дашборда."""

    def test_импортируется(self, dashboard) -> None:
        assert callable(dashboard.main)

    def test_читает_выгрузку(self, dashboard) -> None:
        frame = dashboard.load_frame(FIXTURE)
        assert len(frame) == 11
        assert not frame["archived"].any()

    def test_путь_к_данным_по_умолчанию(self, dashboard) -> None:
        assert dashboard.RAW_DEFAULT.name == "vacancies.json"
        assert dashboard.RAW_DEFAULT.parent.parent.name == "data"

    def test_источник_данных_честно_предупреждает(self, dashboard) -> None:
        # Если настоящей выгрузки нет, источником считается фикстура, и
        # приложение обязано об этом сказать.
        path, is_real = dashboard.data_source()
        assert path.exists()
        if not is_real:
            assert path == dashboard.FIXTURE
