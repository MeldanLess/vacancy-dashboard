"""Сборка вакансий в таблицу и приведение зарплат к общему виду.

Три решения, из-за которых числа в этом проекте можно сравнивать между собой:

1. **Зарплаты «грязные» и «чистые» — это разные числа.** hh.ru честно
   помечает, указана ли зарплата до или после вычета налога. Смешивать их в
   одной медиане нельзя: gross-вакансия на 200 000 ₽ это ~177 000 ₽ на руки.
   Поэтому всё приводится к сумме «на руки» делением на 1,13.
2. **«От» — это нижняя граница, а не зарплата.** Работодатель пишет «от
   150 000», чтобы набрать больше откликов. Медиана нижних границ занижена
   относительно медианы фактических предложений — и это не исправляется
   никакой обработкой. Ограничение названо прямо на графиках.
3. **Вакансии без зарплаты — не нулевые.** Их нельзя выбрасывать молча:
   сколько их было, показывается рядом с каждым подсчётом.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from vacancy_dashboard import features

# НДФЛ в России — 13% с большинства доходов. Зарплата «до вычета» делится
# на 1,13, чтобы получить сумму «на руки». Это допущение, а не факт: у части
# работодателей зарплата «грязная» по договорённости, и её деление может
# дать копейку расхождения. На порядок величин это не влияет.
NET_DIVISOR = 1.13

MOSCOW_TZ = "Europe/Moscow"

# Поля, которые забираются из объекта вакансии hh.ru.
_CURRENCY_RUB = ("RUR", "")


def vacancy_text(vacancy: dict[str, Any]) -> str:
    """Весь текст вакансии одной строкой.

    Складываются название, требования, обязанности, ключевые навыки и роли:
    стек часто упоминается не в названии, а в требованиях, а иногда — только
    в описании обязанностей.
    """
    snippet = vacancy.get("snippet") or {}
    skills = vacancy.get("key_skills") or []
    roles = vacancy.get("professional_roles") or []
    parts = [
        vacancy.get("name") or "",
        snippet.get("requirement") or "",
        snippet.get("responsibility") or "",
        " ".join(str(skill.get("name", "")) for skill in skills),
        " ".join(str(role.get("name", "")) for role in roles),
    ]
    return features.normalize_text(" ".join(part for part in parts if part))


def _salary_parts(salary: dict[str, Any] | None) -> tuple[float | None, float | None, bool]:
    """Зарплата «на руки», потолок и признак «грязная».

    Делим на 1,13 только «грязные» суммы: чистая зарплата уже указана «на
    руки», и деление на НДФЛ занизило бы её на 13%.
    """
    if not salary:
        return None, None, False
    lower = salary.get("from")
    upper = salary.get("to")
    is_gross = bool(salary.get("is_gross"))
    divisor = NET_DIVISOR if is_gross else 1.0
    lower_net = lower / divisor if isinstance(lower, (int, float)) else None
    upper_net = upper / divisor if isinstance(upper, (int, float)) else None
    return lower_net, upper_net, is_gross


def vacancy_to_row(vacancy: dict[str, Any]) -> dict[str, Any]:
    """Одна вакансия → одна строка таблицы."""
    employer = vacancy.get("employer") or {}
    area = vacancy.get("area") or {}
    salary = vacancy.get("salary") or {}
    text = vacancy_text(vacancy)

    salary_net, salary_upper_net, is_gross = _salary_parts(salary)
    currency = salary.get("currency") or ""

    return {
        "id": str(vacancy.get("id") or ""),
        "name": vacancy.get("name") or "",
        "employer": employer.get("name") or "",
        "city": area.get("name") or "",
        "city_group": features.normalize_city(area.get("name")),
        "work_format": features.normalize_work_format(vacancy.get("work_format")),
        "grade": features.extract_grade(vacancy.get("name") or ""),
        "schedule": (vacancy.get("schedule") or {}).get("name") or "",
        "employment": (vacancy.get("employment") or {}).get("name") or "",
        "salary_net": salary_net,
        "salary_upper_net": salary_upper_net,
        "salary_is_gross": is_gross,
        "salary_currency": currency,
        "published_at": vacancy.get("published_at") or "",
        "archived": bool(vacancy.get("archived")),
        "url": vacancy.get("alternate_url") or "",
        "technologies": features.extract_technologies(text),
        "text": text,
    }


def build_frame(vacancies: list[dict[str, Any]]) -> pd.DataFrame:
    """Список вакансий → таблица.

    Дубликаты по `id` отбрасываются: при постраничном сборе hh.ru иногда
    отдаёт одну и ту же вакансию дважды, а в медиане это сдвинуло бы число.
    """
    rows = [vacancy_to_row(vacancy) for vacancy in vacancies]
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame

    frame = frame.drop_duplicates(subset="id").reset_index(drop=True)

    published = pd.to_datetime(frame["published_at"], errors="coerce", utc=True)
    frame["published_at"] = published.dt.tz_convert(MOSCOW_TZ)
    frame["published_month"] = frame["published_at"].dt.strftime("%Y-%m")
    frame["technologies"] = frame["technologies"].apply(list)
    frame["has_salary"] = frame["salary_net"].notna()
    frame["is_russian_salary"] = frame["salary_currency"].isin(_CURRENCY_RUB)
    return frame


def drop_archived(frame: pd.DataFrame) -> pd.DataFrame:
    """Убирает архивные вакансии: они уже не нанимают."""
    return frame.loc[~frame["archived"]].reset_index(drop=True)


def salary_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Подмножество вакансий, пригодных для подсчёта зарплат.

    Остаются только вакансии, где зарплата указана в рублях. Всё, что
    отсеяно, возвращается отдельным числом — его показывают на графиках.
    """
    usable = frame.loc[frame["has_salary"] & frame["is_russian_salary"]]
    return usable.reset_index(drop=True)


def technology_counts(frame: pd.DataFrame) -> pd.Series:
    """Сколько вакансий упоминают каждую технологию.

    Считаются вакансии, а не упоминания: одна вакансия с тремя разами
    упомянутым Docker — это одна вакансия.
    """
    counter: dict[str, int] = {}
    for technologies in frame["technologies"]:
        for technology in technologies:
            counter[technology] = counter.get(technology, 0) + 1
    return pd.Series(counter, dtype="int64").sort_values(ascending=False)


def technology_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    """Таблица «вакансия × технология» — 1, если технология упомянута.

    Из неё считаются доли (какая доля вакансий требует PostgreSQL) и
    совместные упоминания (Python и FastAPI вместе).
    """
    all_technologies = sorted({tech for techs in frame["technologies"] for tech in techs})
    if not all_technologies:
        return pd.DataFrame(index=frame.index)
    matrix = pd.DataFrame(
        0,
        index=frame.index,
        columns=all_technologies,
        dtype="int8",
    )
    for row_index, technologies in zip(frame.index, frame["technologies"], strict=True):
        for technology in technologies:
            matrix.at[row_index, technology] = 1
    return matrix
