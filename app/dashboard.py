"""Дашборд по вакансиям hh.ru — приложение на Streamlit.

Запуск:

    streamlit run app/dashboard.py

Приложение показывает то же, что и ноутбуки: три вопроса к рынку, графики
и таблицы. Данные берутся из локальной выгрузки — сеть не нужна, поэтому
приложение работает и без интернета, и без токена hh.ru.

Как получить данные:

    python -m vacancy_dashboard.collect --text python --pages 20

Всё, что приложение показывает, считается из выгрузки на лету: при смене
фильтров числа пересчитываются, а не берутся из готовой картинки.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
# Пакет лежит рядом с приложением, но не установлен: добавляем корень
# репозитория в путь импорта, чтобы дашборд запускался из любого каталога.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vacancy_dashboard import analysis, clean, collect, config  # noqa: E402

RAW_DEFAULT = ROOT / "data" / "raw" / "vacancies.json"
FIXTURE = ROOT / "tests" / "fixtures" / "vacancies_sample.json"

# Путь к данным можно переопределить переменной окружения: так дашборд
# открывают на своей выгрузке, а тест — на фикстуре.
DATA_ENV = "VACANCY_DASHBOARD_DATA"


def load_frame(path: Path) -> pd.DataFrame:
    """Выгрузка вакансий → таблица без архивных."""
    vacancies = collect.load(path)
    return clean.drop_archived(clean.build_frame(vacancies))


def data_source() -> tuple[Path, bool]:
    """Путь к данным и признак того, что это настоящая выгрузка.

    Если выгрузки нет, приложение показывает синтетическую фикстуру и честно
    предупреждает об этом: рыночные числа из фикстуры делать нельзя.

    Переменная окружения `VACANCY_DASHBOARD_DATA` переопределяет путь: так
    дашборд открывают на своей выгрузке, а тест — на фикстуре, независимо от
    того, лежит ли настоящая выгрузка рядом.
    """
    override = os.environ.get(DATA_ENV)
    if override:
        path = Path(override)
        return path, path.resolve() != FIXTURE.resolve()
    if RAW_DEFAULT.exists():
        return RAW_DEFAULT, True
    return FIXTURE, False


def sidebar(frame: pd.DataFrame) -> pd.DataFrame:
    """Фильтры в боковой панели.

    По умолчанию выбрано всё, включая вакансии без названного уровня
    должности: иначе часть выборки молча исчезла бы из ответов, а счётчик
    «Вакансий» вверху показывал бы число больше, чем в ответах.
    """
    st.sidebar.header("Фильтры")

    city_groups = sorted(frame["city_group"].unique())
    chosen_cities = st.sidebar.multiselect("Группа городов", city_groups, default=city_groups)

    grades = [*config.GRADE_ORDER, config.GRADE_UNKNOWN]
    chosen_grades = st.sidebar.multiselect("Уровень должности", grades, default=grades)

    with_salary = st.sidebar.checkbox("Только вакансии с зарплатой", value=False)

    filtered = frame[frame["city_group"].isin(chosen_cities)]
    filtered = filtered[filtered["grade"].isin(chosen_grades)]
    if with_salary:
        filtered = filtered[filtered["has_salary"]]

    st.sidebar.caption(f"После фильтров: {len(filtered)} из {len(frame)}")
    return filtered


def show_answer(result: analysis.QuestionResult, figure: object) -> None:
    """Один ответ: заголовок, текст, таблица и график."""
    st.subheader(result.title)
    st.write(result.text)
    st.dataframe(result.table)
    st.pyplot(figure)


def main() -> None:
    """Сборка страницы."""
    st.set_page_config(page_title="Вакансии hh.ru: три вопроса", layout="wide")
    st.title("Вакансии hh.ru: три вопроса к рынку")

    path, is_real = data_source()
    if not path.exists():
        st.error(f"Файл с данными не найден: {path}")
        return
    if not is_real:
        st.warning(
            "Настоящей выгрузки нет — приложение показывает синтетическую фикстуру. "
            "Числа оттуда нельзя использовать в резюме: сначала выполните сбор "
            "(`python -m vacancy_dashboard.collect`).",
            icon="⚠️",
        )
    st.caption(f"Данные: {path}")

    frame = load_frame(path)
    if frame.empty:
        st.error("В выгрузке нет ни одной неархивной вакансии.")
        return

    summary = analysis.dataset_summary(frame)
    columns = st.columns(4)
    columns[0].metric("Вакансий", summary["вакансий"])
    columns[1].metric("С зарплатой", summary["с зарплатой"])
    columns[2].metric("Городов", summary["городов"])
    columns[3].metric("Технологий", summary["технологий"])
    st.caption(f"Период публикаций: {summary['период']}")

    filtered = sidebar(frame)
    if filtered.empty:
        st.warning("Под фильтры не попала ни одна вакансия — ослабьте условия.")
        return

    stack, stack_figure = analysis.question_stack(filtered)
    show_answer(stack, stack_figure)

    geography, geography_figure = analysis.question_geography(filtered)
    show_answer(geography, geography_figure)

    experience, experience_figure = analysis.question_experience(filtered)
    show_answer(experience, experience_figure)

    st.subheader("Динамика по месяцам")
    technologies = list(stack.table["Технология"][:5])
    months = analysis.stack_by_month(filtered, technologies)
    st.dataframe(months.round(1))
    st.pyplot(analysis.monthly_trend(filtered, technologies))
    st.caption(
        "В таблице — доля вакансий с каждой технологией по месяцам публикации, "
        "в процентах от числа вакансий за месяц."
    )

    st.subheader("Сырые данные")
    st.dataframe(filtered.drop(columns=["text"]))


if __name__ == "__main__":
    main()
