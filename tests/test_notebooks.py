"""Ноутбуки должны совпадать со скриптом сборки.

Скрипт `scripts/build_notebooks.py` — единственный источник правды для
каталога `notebooks/`. Если скрипт изменился, а ноутбуки забыли пересобрать,
код в ноутбуке разойдётся с кодом пайплайна. CI ловит это сравнением файлов,
а этот тест делает то же самое локально и за секунду.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_notebooks  # noqa: E402

NOTEBOOK_NAMES = sorted(build_notebooks.NOTEBOOKS)


class TestNotebooks:
    """Ноутбуки совпадают со скриптом сборки."""

    @pytest.mark.parametrize("name", NOTEBOOK_NAMES)
    def test_файл_совпадает_со_скриптом(self, name: str) -> None:
        """Файл ноутбука — побайтово то, что собирает скрипт."""
        cells = build_notebooks.NOTEBOOKS[name]
        expected = (
            json.dumps(build_notebooks.build_notebook(cells), ensure_ascii=False, indent=1) + "\n"
        ).encode("utf-8")
        actual = (ROOT / "notebooks" / name).read_bytes()
        assert actual == expected, (
            f"{name} разошёлся со скриптом сборки: выполните "
            "`python scripts/build_notebooks.py` и закоммитите результат"
        )

    @pytest.mark.parametrize("name", NOTEBOOK_NAMES)
    def test_ноутбук_читается_и_имеет_идентификаторы(self, name: str) -> None:
        """Ноутбук — корректный JSON, у каждой ячейки есть идентификатор."""
        notebook = json.loads((ROOT / "notebooks" / name).read_text(encoding="utf-8"))
        assert notebook["nbformat"] == 4
        assert notebook["nbformat_minor"] == 5
        assert notebook["cells"]
        for cell in notebook["cells"]:
            assert cell["id"]
