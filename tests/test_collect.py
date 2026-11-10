"""Тесты сборщика вакансий: параметры, заголовки, повторы при сбое.

Сеть в тестах не используется: подменяется сессия `requests`, чтобы
проверять поведение при ошибках и лимитах API.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from vacancy_dashboard import collect, config


class FakeResponse:
    """Ответ сервера: статус, тело и заголовки."""

    def __init__(
        self,
        status_code: int = 200,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        text: str = "",
    ) -> None:
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}
        self.text = text

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeSession:
    """Сессия-заглушка: отдаёт заранее подготовленные ответы по порядку."""

    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def __enter__(self) -> FakeSession:
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> FakeResponse:
        self.calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
        if not self.responses:
            raise AssertionError("Тест запросил больше ответов, чем подготовлено")
        return self.responses.pop(0)


@pytest.fixture(autouse=True)
def _без_пауз(monkeypatch: pytest.MonkeyPatch) -> None:
    """Паузы при повторах не нужны: они замедлили бы тесты на минуты."""
    monkeypatch.setattr(collect.time, "sleep", lambda _seconds: None)


class TestSettings:
    """Параметры запроса."""

    def test_базовые_параметры(self) -> None:
        settings = collect.CollectSettings(text="python", area=113, per_page=100)
        params = settings.params(0)
        assert params["text"] == "python"
        assert params["area"] == 113
        assert params["page"] == 0
        assert params["per_page"] == 100
        assert params["order_by"] == "publication_time"

    def test_больше_ста_на_страницу_api_не_принимает(self) -> None:
        settings = collect.CollectSettings(per_page=500)
        assert settings.params(0)["per_page"] == 100

    def test_фильтр_по_зарплате(self) -> None:
        settings = collect.CollectSettings(only_with_salary=True)
        assert settings.params(0)["only_with_salary"] == "true"

    def test_период_в_днях(self) -> None:
        settings = collect.CollectSettings(period_days=7)
        assert settings.params(0)["period"] == 7

    def test_дополнительные_параметры(self) -> None:
        settings = collect.CollectSettings(extra={"search_field": "name"})
        assert settings.params(0)["search_field"] == "name"


class TestHeaders:
    """Заголовки запроса."""

    def test_user_agent_обязателен(self) -> None:
        # Без User-Agent hh.ru отвечает 403: это самая частая причина
        # пустой выгрузки.
        headers = collect.CollectSettings().headers()
        assert headers["User-Agent"]
        assert "@" in headers["User-Agent"]

    def test_токен_даёт_заголовок_authorization(self) -> None:
        headers = collect.CollectSettings(token="секрет").headers()
        assert headers["Authorization"] == "Bearer секрет"

    def test_без_токена_authorization_нет(self) -> None:
        headers = collect.CollectSettings().headers()
        assert "Authorization" not in headers


class TestFetchPage:
    """Повторы при сбоях."""

    def test_успешный_ответ_с_разу(self) -> None:
        session = FakeSession([FakeResponse(200, {"items": [1], "pages": 1})])
        payload = collect.fetch_page(session, collect.CollectSettings(), 0)
        assert payload["items"] == [1]
        assert len(session.calls) == 1

    def test_повтор_при_ошибке_сервера(self) -> None:
        session = FakeSession(
            [FakeResponse(500, text="позже"), FakeResponse(200, {"items": [], "pages": 1})]
        )
        payload = collect.fetch_page(session, collect.CollectSettings(), 0)
        assert payload["items"] == []
        assert len(session.calls) == 2

    def test_после_четырёх_попыток_ошибка(self) -> None:
        session = FakeSession([FakeResponse(500, text="позже") for _ in range(4)])
        with pytest.raises(collect.CollectError):
            collect.fetch_page(session, collect.CollectSettings(), 0)
        assert len(session.calls) == collect.MAX_ATTEMPTS

    def test_отказ_403_не_повторяется(self) -> None:
        # 403 — это «неправильный запрос», а не временная ошибка: повторять
        # бессмысленно.
        session = FakeSession([FakeResponse(403, text="нужен User-Agent")])
        with pytest.raises(collect.CollectError):
            collect.fetch_page(session, collect.CollectSettings(), 0)
        assert len(session.calls) == 1

    def test_лимит_запросов_не_превышен(self) -> None:
        session = FakeSession([FakeResponse(200, {"items": [], "pages": 1})])
        collect.fetch_page(session, collect.CollectSettings(), 0)
        assert len(session.calls) <= collect.MAX_ATTEMPTS


class TestCollect:
    """Постраничный сбор."""

    def test_собирает_все_страницы(self, monkeypatch: pytest.MonkeyPatch) -> None:
        session = FakeSession(
            [
                FakeResponse(200, {"items": [{"id": "1"}], "pages": 2}),
                FakeResponse(200, {"items": [{"id": "2"}], "pages": 2}),
            ]
        )
        monkeypatch.setattr(collect.requests, "Session", lambda: session)
        vacancies = collect.collect(collect.CollectSettings(max_pages=5))
        assert [item["id"] for item in vacancies] == ["1", "2"]
        assert len(session.calls) == 2

    def test_останавливается_на_пустой_странице(self, monkeypatch: pytest.MonkeyPatch) -> None:
        session = FakeSession([FakeResponse(200, {"items": [], "pages": 5})])
        monkeypatch.setattr(collect.requests, "Session", lambda: session)
        assert collect.collect(collect.CollectSettings(max_pages=5)) == []
        assert len(session.calls) == 1

    def test_не_превышает_заданное_число_страниц(self, monkeypatch: pytest.MonkeyPatch) -> None:
        session = FakeSession(
            [FakeResponse(200, {"items": [{"id": str(i)}], "pages": 100}) for i in range(3)]
        )
        monkeypatch.setattr(collect.requests, "Session", lambda: session)
        vacancies = collect.collect(collect.CollectSettings(max_pages=2))
        assert len(vacancies) == 2


class TestSaveLoad:
    """Сохранение и чтение сырого JSON."""

    def test_круг_сохранения(self, tmp_path) -> None:
        vacancies = [{"id": "1", "name": "Python разработчик"}]
        target = collect.save(vacancies, tmp_path / "raw" / "vacancies.json")
        assert target.exists()
        assert collect.load(target) == vacancies

    def test_кириллица_не_ломается(self, tmp_path) -> None:
        vacancies = [{"id": "1", "name": "Разработчик"}]
        target = collect.save(vacancies, tmp_path / "vacancies.json")
        raw = target.read_text(encoding="utf-8")
        assert "Разработчик" in raw
        assert json.loads(raw) == vacancies


class TestSettingsFromEnv:
    """Настройки из переменных окружения."""

    def test_токен_берётся_из_окружения(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HH_TOKEN", "токен-из-окружения")
        monkeypatch.setenv("HH_USER_AGENT", "vacancy-dashboard (test@example.com)")
        settings = collect.settings_from_env()
        assert settings.token == "токен-из-окружения"
        assert settings.user_agent == "vacancy-dashboard (test@example.com)"

    def test_без_переменных_токена_нет(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("HH_TOKEN", raising=False)
        monkeypatch.delenv("HH_USER_AGENT", raising=False)
        settings = collect.settings_from_env()
        assert settings.token is None
        assert settings.user_agent == config.DEFAULT_USER_AGENT


class TestMain:
    """Запуск из командной строки."""

    def test_собирает_и_сохраняет(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Сеть не используется: подменяется сам сбор.
        monkeypatch.setattr(collect, "collect", lambda _settings: [{"id": "1"}])
        target = tmp_path / "raw" / "vacancies.json"
        code = collect.main(["--text", "python", "--out", str(target)])
        assert code == 0
        assert collect.load(target) == [{"id": "1"}]

    def test_параметры_команды_доходят_до_сборщика(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, Any] = {}

        def fake_collect(settings: collect.CollectSettings) -> list[dict[str, Any]]:
            captured["text"] = settings.text
            captured["max_pages"] = settings.max_pages
            captured["only_with_salary"] = settings.only_with_salary
            return []

        monkeypatch.setattr(collect, "collect", fake_collect)
        collect.main(
            [
                "--text",
                "golang",
                "--pages",
                "3",
                "--only-with-salary",
                "--out",
                str(tmp_path / "vacancies.json"),
            ]
        )
        assert captured["text"] == "golang"
        assert captured["max_pages"] == 3
        assert captured["only_with_salary"] is True
