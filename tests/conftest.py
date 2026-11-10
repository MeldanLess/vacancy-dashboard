"""Общие фикстуры тестов.

Фикстура в `fixtures/vacancies_sample.json` — **синтетическая**: она собрана
вручную в форме ответа API hh.ru, чтобы тесты не ходили в сеть и не зависели
от того, что hh.ru сегодня отдаёт. Рыночные числа этого проекта берутся из
настоящей выгрузки, а не из фикстуры.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def sample_vacancies() -> list[dict[str, Any]]:
    """Список вакансий из фикстуры — как приходит от API."""
    path = FIXTURES_DIR / "vacancies_sample.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def sample_frame(sample_vacancies: list[dict[str, Any]]):
    """Готовая таблица по фикстуре, без архивных вакансий."""
    from vacancy_dashboard import clean

    return clean.drop_archived(clean.build_frame(sample_vacancies))
