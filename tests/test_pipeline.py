"""Тесты пайплайна: сборка таблицы, сохранение и запуск целиком."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from vacancy_dashboard import pipeline

FIXTURE = Path(__file__).parent / "fixtures" / "vacancies_sample.json"


class TestBuild:
    """Сырой JSON → таблица."""

    def test_архивные_убираются(self) -> None:
        frame = pipeline.build(FIXTURE)
        assert len(frame) == 11
        assert not frame["archived"].any()


class TestSaveTable:
    """Сохранение таблицы в CSV."""

    def test_таблица_сохраняется(self, tmp_path: Path) -> None:
        frame = pipeline.build(FIXTURE)
        target = pipeline.save_table(frame, tmp_path / "processed")
        assert target.exists()
        table = pd.read_csv(target, encoding="utf-8")
        assert len(table) == len(frame)

    def test_сырой_текст_в_таблицу_не_попадает(self, tmp_path: Path) -> None:
        # Текст вакансии нужен для разбора, но в CSV он только раздувает файл.
        frame = pipeline.build(FIXTURE)
        target = pipeline.save_table(frame, tmp_path / "processed")
        table = pd.read_csv(target, encoding="utf-8")
        assert "text" not in table.columns

    def test_технологии_склеены_в_строку(self, tmp_path: Path) -> None:
        frame = pipeline.build(FIXTURE)
        target = pipeline.save_table(frame, tmp_path / "processed")
        table = pd.read_csv(target, encoding="utf-8")
        assert "Python" in table["technologies"].iloc[0]


class TestRun:
    """Полный прогон."""

    def test_даёт_три_ответа(self, tmp_path: Path) -> None:
        _, results = pipeline.run(
            FIXTURE,
            tmp_path / "processed",
            tmp_path / "figures",
        )
        assert len(results) == 3
        assert {result.key for result in results} == {"stack", "geography", "experience"}

    def test_графики_сохраняются(self, tmp_path: Path) -> None:
        _, results = pipeline.run(
            FIXTURE,
            tmp_path / "processed",
            tmp_path / "figures",
        )
        for result in results:
            assert (tmp_path / "figures" / result.figure_name).exists()


class TestMain:
    """Запуск из командной строки."""

    def test_печатает_сводку(self, tmp_path: Path, capsys) -> None:
        code = pipeline.main(
            [
                "--input",
                str(FIXTURE),
                "--output-dir",
                str(tmp_path / "processed"),
                "--figures-dir",
                str(tmp_path / "figures"),
            ]
        )
        assert code == 0
        output = capsys.readouterr().out
        assert "=== Выборка ===" in output
        assert "=== Ответы ===" in output

    def test_пишет_сводку_в_файл(self, tmp_path: Path) -> None:
        pipeline.main(
            [
                "--input",
                str(FIXTURE),
                "--output-dir",
                str(tmp_path / "processed"),
                "--figures-dir",
                str(tmp_path / "figures"),
            ]
        )
        summary_path = tmp_path / "processed" / "summary.json"
        assert summary_path.exists()
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        assert summary["вакансий"] == 11
        assert summary["с зарплатой"] == 10
