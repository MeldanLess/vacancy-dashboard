"""Тесты объяснений отказов hh.ru.

Ошибка API без объяснения бесполезна: «forbidden» не говорит, что делать.
Здесь проверяется, что известные причины превращаются в понятную строку.
"""

from __future__ import annotations

from vacancy_dashboard.collect import explain


class TestExplain:
    """Каждый известный отказ — с человеческим объяснением."""

    def test_без_токена(self) -> None:
        hint = explain(403, '{"errors":[{"type":"forbidden"}]}')
        assert "dev.hh.ru/admin" in hint
        assert "HH_TOKEN" in hint

    def test_чёрный_список_user_agent(self) -> None:
        hint = explain(400, '{"errors":[{"type":"bad_user_agent","value":"blacklisted"}]}')
        assert "User-Agent" in hint
        assert "HH_USER_AGENT" in hint

    def test_неизвестный_отказ_остаётся_как_есть(self) -> None:
        assert explain(500, "oops") == ""

    def test_ошибка_без_подсказки(self) -> None:
        assert explain(404, "not found") == ""
