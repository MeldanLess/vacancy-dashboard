"""Три вопроса к данным и графики к ним.

Правило, которому подчинены все три ответа: **число, которое нельзя
проверить, не публикуется**. Медиана без указания размера выборки, доля без
знаменателя и «в среднем 150 000 ₽» без указания, что это нижние границы —
всё это способы соврать аккуратно и незаметно. Поэтому каждый график
сопровождается числом вакансий, на которых он построен, а каждая таблица
содержит количество наблюдений в группе.

Каждый вопрос возвращает: таблицу, один абзац интерпретации и один график.
Оформление графиков вынесено в `charts.py` — здесь только числа.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from vacancy_dashboard import charts, clean, config, features
from vacancy_dashboard.charts import money, percent

# Группы, где наблюдений меньше этого числа, показываются отдельной
# строкой «немало данных» — медиана по десяти вакансиям не является
# характеристикой рынка.
MIN_GROUP_SIZE = 30

# Сколько технологий попадает в топ на графике.
TOP_TECHNOLOGIES = 15


@dataclass
class QuestionResult:
    """Ответ на один вопрос: таблица, текст и имя файла с графиком."""

    key: str
    title: str
    table: pd.DataFrame
    text: str
    figure_name: str

    def save_figure(self, figure: plt.Figure, directory: Path) -> Path:
        """Сохраняет график и возвращает путь к файлу."""
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / self.figure_name
        figure.savefig(target, dpi=charts.FIGURE_DPI, bbox_inches="tight")
        plt.close(figure)
        return target


def _ratio(value: float) -> str:
    """Коэффициент в русской записи: 2,5 раза."""
    return f"{value:.1f}".replace(".", ",")


def _plural(count: int, one: str, few: str, many: str) -> str:
    """Русское склонение числительных: 1 вакансия, 2 вакансии, 5 вакансий."""
    tail = count % 100
    if 11 <= tail <= 14:
        return many
    tail %= 10
    if tail == 1:
        return one
    if 2 <= tail <= 4:
        return few
    return many


def _vacancies(count: int) -> str:
    """Количество вакансий словами: «3 вакансии»."""
    return f"{count} {_plural(count, 'вакансия', 'вакансии', 'вакансий')}"


def _vacancies_genitive(count: int) -> str:
    """Количество вакансий в родительном падеже: «из 1 вакансии»."""
    word = "вакансии" if count % 10 == 1 and count % 100 != 11 else "вакансий"
    return f"{count} {word}"


# ---------------------------------------------------------------------------
# Вопрос 1. Какие технологии просят чаще всего
# ---------------------------------------------------------------------------


def question_stack(frame: pd.DataFrame) -> tuple[QuestionResult, plt.Figure]:
    """Топ технологий и как менялась их доля по месяцам."""
    counts = clean.technology_counts(frame)
    total = len(frame)
    table = pd.DataFrame(
        {
            "Технология": counts.index,
            "Вакансий": counts.values,
            "Доля, %": (counts.values / total * 100).round(1) if total else 0,
        }
    )
    table["Категория"] = [features.technology_category(name) for name in table["Технология"]]
    table = table.head(TOP_TECHNOLOGIES).reset_index(drop=True)

    figure = charts.stack_chart(table, total)

    if table.empty:
        text = "В выборке не нашлось ни одной технологии — текст вакансий разбирать не из чего."
    else:
        leader = table.iloc[0]
        second = table.iloc[1] if len(table) > 1 else None
        text = (
            f"Чаще всего просят {leader['Технология']} — {leader['Вакансий']} вакансий из {total}, "
            f"то есть {percent(leader['Доля, %'])} выборки."
        )
        if second is not None:
            gap = float(leader["Доля, %"]) - float(second["Доля, %"])
            if gap == 0:
                text += (
                    f" На втором месте — {second['Технология']} "
                    f"({percent(second['Доля, %'])}): делит первое место с лидером."
                )
            else:
                text += (
                    f" Второе место — {second['Технология']} "
                    f"({percent(second['Доля, %'])}): разрыв с лидером {percent(gap)}."
                )
        text += (
            " Доли считаются по вакансиям, а не по упоминаниям: одна вакансия, "
            "где Python назван трижды, попадает в счётчик один раз."
        )
    return (
        QuestionResult(
            key="stack",
            title="Какие технологии просят чаще всего",
            table=table,
            text=text,
            figure_name="q1_stack.png",
        ),
        figure,
    )


def stack_by_month(frame: pd.DataFrame, technologies: list[str]) -> pd.DataFrame:
    """Доля вакансий с каждой технологией по месяцам публикации."""
    rows = []
    for month, group in frame.groupby("published_month", dropna=True):
        counts = clean.technology_counts(group)
        row = {"Месяц": month, "Вакансий": len(group)}
        for technology in technologies:
            row[technology] = counts.get(technology, 0) / len(group) * 100
        rows.append(row)
    return pd.DataFrame(rows)


def monthly_trend(frame: pd.DataFrame, technologies: list[str]) -> plt.Figure:
    """График динамики по месяцам для выбранных технологий."""
    months = stack_by_month(frame, technologies)
    return charts.monthly_trend_chart(months, technologies)


def save_trend(
    frame: pd.DataFrame,
    figures_dir: Path,
    technologies: list[str] | None = None,
) -> Path:
    """Сохраняет график динамики по месяцам.

    Если технологии не заданы, берутся пять лидеров из первого вопроса.
    """
    if technologies is None:
        counts = clean.technology_counts(frame)
        technologies = list(counts.index[:5])
    figure = monthly_trend(frame, technologies)
    figures_dir.mkdir(parents=True, exist_ok=True)
    target = figures_dir / "q1_stack_by_month.png"
    figure.savefig(target, dpi=charts.FIGURE_DPI, bbox_inches="tight")
    plt.close(figure)
    return target


# ---------------------------------------------------------------------------
# Вопрос 2. Где платят больше
# ---------------------------------------------------------------------------


def question_geography(frame: pd.DataFrame) -> tuple[QuestionResult, plt.Figure]:
    """Медиана предложения «на руки» по группам городов."""
    usable = clean.salary_frame(frame)
    dropped = len(frame) - len(usable)

    if usable.empty:
        empty = pd.DataFrame(columns=["Группа", "Вакансий", "Медиана, ₽"])
        figure = charts.geography_chart(empty)
        return (
            QuestionResult(
                key="geography",
                title="Где платят больше",
                table=empty,
                text="В выборке нет ни одной вакансии с указанной зарплатой — считать нечего.",
                figure_name="q2_geography.png",
            ),
            figure,
        )

    grouped = usable.groupby("city_group")["salary_net"].agg(["count", "median"]).reset_index()
    grouped = grouped.rename(
        columns={"city_group": "Группа", "count": "Вакансий", "median": "Медиана, ₽"}
    )
    grouped["Медиана, ₽"] = grouped["Медиана, ₽"].round(-2)
    grouped["Доля, %"] = (grouped["Вакансий"] / len(usable) * 100).round(1)
    grouped = grouped.sort_values("Медиана, ₽", ascending=False).reset_index(drop=True)

    order = [
        config.MOSCOW,
        config.SAINT_PETERSBURG,
        config.OTHER_MILLION,
        config.REMOTE,
        config.REGION,
    ]
    grouped["_порядок"] = grouped["Группа"].map({name: i for i, name in enumerate(order)})
    grouped = grouped.sort_values("_порядок").drop(columns="_порядок").reset_index(drop=True)

    figure = charts.geography_chart(grouped)

    moscow_row = grouped[grouped["Группа"] == config.MOSCOW]
    region_row = grouped[grouped["Группа"] == config.REGION]
    text = (
        f"В выборке {len(usable)} вакансий с указанной зарплатой. "
        f"Без зарплаты — ещё {_vacancies(dropped)}; такие вакансии не считаются нулевыми."
    )
    if not moscow_row.empty and not region_row.empty:
        moscow = float(moscow_row.iloc[0]["Медиана, ₽"])
        region = float(region_row.iloc[0]["Медиана, ₽"])
        if region > 0:
            text += (
                f" Медиана в Москве — {money(moscow)}, в регионах — {money(region)}, "
                f"разрыв {_ratio(moscow / region)} раза."
            )
    best = grouped.iloc[0]
    text += (
        f" Самая высокая медиана — у группы «{best['Группа']}» "
        f"({money(float(best['Медиана, ₽']))}, n = {best['Вакансий']})."
        " Все числа — нижние границы вилок «от», а не фактические зарплаты."
    )
    small = grouped[grouped["Вакансий"] < MIN_GROUP_SIZE]
    if not small.empty:
        names = ", ".join(f"«{name}»" for name in small["Группа"])
        text += f" Для групп {names} наблюдений меньше {MIN_GROUP_SIZE} — их медиана шумная."

    return (
        QuestionResult(
            key="geography",
            title="Где платят больше",
            table=grouped,
            text=text,
            figure_name="q2_geography.png",
        ),
        figure,
    )


# ---------------------------------------------------------------------------
# Вопрос 3. Сколько стоит опыт
# ---------------------------------------------------------------------------


def question_experience(frame: pd.DataFrame) -> tuple[QuestionResult, plt.Figure]:
    """Медиана по уровню должности и доля удалённой работы."""
    usable = clean.salary_frame(frame)
    grades = [grade for grade in config.GRADE_ORDER if grade != config.GRADE_UNKNOWN]
    unknown_count = int((frame["grade"] == config.GRADE_UNKNOWN).sum())

    rows = []
    for grade in grades:
        subset = usable[usable["grade"] == grade]
        all_at_grade = frame[frame["grade"] == grade]
        if all_at_grade.empty:
            # Уровня нет в выборке: строка была бы нулевой и мешала читать
            # остальные.
            continue
        remote_share = (all_at_grade["work_format"] == config.WORK_FORMATS["REMOTE"]).mean() * 100
        median = round(float(subset["salary_net"].median()), -2) if len(subset) else None
        rows.append(
            {
                "Уровень": grade,
                "Вакансий": len(subset),
                "Всего": len(all_at_grade),
                "Медиана, ₽": median,
                "Удалённо, %": round(remote_share, 1),
            }
        )
    table = pd.DataFrame(rows)

    figure = charts.experience_chart(table, len(usable))

    junior = (
        table[table["Уровень"] == "Junior"]["Медиана, ₽"]
        if not table.empty
        else pd.Series(dtype="float64")
    )
    senior = (
        table[table["Уровень"] == "Senior"]["Медиана, ₽"]
        if not table.empty
        else pd.Series(dtype="float64")
    )
    text = (
        f"Уровень должности удалось определить по названию у {len(frame) - unknown_count} "
        f"вакансий из {len(frame)}; в {unknown_count} он не назван — их медиана отдельно "
        "не считается, потому что «не указан» — это не уровень."
    )
    junior_value = float(junior.iloc[0]) if not junior.empty and pd.notna(junior.iloc[0]) else 0.0
    senior_value = float(senior.iloc[0]) if not senior.empty and pd.notna(senior.iloc[0]) else 0.0
    if junior_value > 0 and senior_value > 0:
        ratio = senior_value / junior_value
        text += (
            f" Медиана у senior — {money(senior_value)}, у junior — "
            f"{money(junior_value)}: разрыв {_ratio(ratio)} раза."
        )
    if not table.empty:
        best_remote = table.loc[table["Удалённо, %"].idxmax()]
        remote_count = _vacancies_genitive(int(best_remote["Всего"]))
        text += (
            f" Больше всего удалённой работы — на уровне «{best_remote['Уровень']}» "
            f"({percent(float(best_remote['Удалённо, %']))} из {remote_count})."
        )
        small = table[table["Всего"] < MIN_GROUP_SIZE]
        if not small.empty:
            names = ", ".join(f"«{name}»" for name in small["Уровень"])
            text += (
                f" Для уровней {names} вакансий меньше {MIN_GROUP_SIZE} — "
                "эти доли и медианы показывают шум, а не рынок."
            )
    text += " Зарплаты, как и везде в этом проекте, — нижние границы вилок «от»."

    return (
        QuestionResult(
            key="experience",
            title="Сколько стоит опыт",
            table=table,
            text=text,
            figure_name="q3_experience.png",
        ),
        figure,
    )


# ---------------------------------------------------------------------------
# Общий запуск
# ---------------------------------------------------------------------------


def run_all(frame: pd.DataFrame, figures_dir: Path) -> list[QuestionResult]:
    """Считает все три ответа и сохраняет графики."""
    results: list[QuestionResult] = []
    for builder in (question_stack, question_geography, question_experience):
        result, figure = builder(frame)
        result.save_figure(figure, figures_dir)
        results.append(result)
    return results


def dataset_summary(frame: pd.DataFrame) -> dict[str, object]:
    """Короткая сводка по выборке — она печатается в консоль и в README."""
    if frame.empty:
        return {
            "вакансий": 0,
            "с зарплатой": 0,
            "без зарплаты": 0,
            "городов": 0,
            "компаний": 0,
            "технологий": 0,
            "период": "неизвестно",
        }
    usable = clean.salary_frame(frame)
    return {
        "вакансий": int(len(frame)),
        "с зарплатой": int(len(usable)),
        "без зарплаты": int(len(frame) - len(usable)),
        "городов": int(frame["city"].nunique()),
        "компаний": int(frame["employer"].nunique()),
        "технологий": int(len(clean.technology_counts(frame))),
        "период": (
            f"{frame['published_at'].min():%Y-%m} — {frame['published_at'].max():%Y-%m}"
            if not frame.empty and frame["published_at"].notna().any()
            else "неизвестно"
        ),
    }
