"""Оформление графиков.

Правила, которым подчинены все графики проекта:

* **Одна ось.** Двух шкал на одном графике не бывает: две меры разного
  порядка — это два графика рядом, а не одна картинка с двумя осями Y.
  Совмещённые шкалы придумывают связь, которой в данных нет.
* **Одна серия — один цвет.** Цветом кодируют разные сущности, а не
  величину: столбцы одной серии не раскрашиваются градиентом, иначе цвет
  повторяет длину столбца и тратит единственный свободный канал впустую.
* **Подписи выборочные.** Число стоит у лидеров, а не у каждого столбца:
  иначе график превращается в таблицу и перестаёт читаться формой.
* **Сетка и оси — волосяные.** Они отступают данным, а не спорят с ними.
* **Таблица рядом.** У каждого графика есть таблица-двойник: все значения
  доступны текстом, поэтому цвет и подпись никогда не единственный носитель
  смысла.

Палитра взята из справочника по чтению графиков: цвета проверены на
различимость при дальтонизме и на контраст с фоном.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # сервер без экрана: рисуем в файл, а не на окно

import matplotlib.pyplot as plt
import pandas as pd

# Фон, текст и линии.
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

# Категориальные цвета: первые пять слотов проверены на различимость при
# дальтонизме (худшая соседняя пара ΔE 9.1 при пороге 8).
SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4")

# Сколько лидеров подписываем числом. Остальные читаются по оси.
LABELLED_BARS = 5

# Размер картинок в пикселях: 160×90 при 100 dpi даёт файл, который читается
# и на телефоне, и в PDF.
FIGURE_SIZE = (16, 9)
FIGURE_DPI = 100


def money(value: float) -> str:
    """Деньги в читаемом виде: 150 000 ₽."""
    return f"{value:,.0f}".replace(",", " ") + " ₽"


def percent(value: float) -> str:
    """Процент в русской записи: 63,6 %."""
    return f"{value:.1f} %".replace(".", ",")


def _style() -> None:
    """Общие настройки оформления для всех графиков."""
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",  # в нём есть кириллица
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "axes.edgecolor": AXIS,
            "axes.labelcolor": INK_SECONDARY,
            "axes.titlecolor": INK,
            "axes.titlesize": 15,
            "axes.titlepad": 16,
            "axes.labelsize": 12,
            "axes.grid": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "xtick.color": INK_MUTED,
            "ytick.color": INK_MUTED,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "grid.color": GRID,
            "grid.linewidth": 0.8,
            "legend.frameon": False,
            "figure.dpi": FIGURE_DPI,
        }
    )


def _figure(
    title: str,
    xlabel: str = "",
    ylabel: str = "",
    figsize: tuple[float, float] = FIGURE_SIZE,
) -> tuple[plt.Figure, plt.Axes]:
    """Новая фигура с общим оформлением."""
    _style()
    figure, axes = plt.subplots(figsize=figsize)
    axes.set_title(title, fontsize=15, pad=16)
    axes.set_xlabel(xlabel)
    axes.set_ylabel(ylabel)
    axes.grid(axis="y", alpha=1.0, linewidth=0.8)
    axes.set_axisbelow(True)
    return figure, axes


def stack_chart(table: pd.DataFrame, total: int) -> plt.Figure:
    """Топ технологий: горизонтальные столбцы, один цвет."""
    figure, axes = _figure(
        f"Топ-{len(table)} технологий по числу вакансий (n = {total})",
        "Вакансий",
    )
    if table.empty:
        axes.text(
            0.5,
            0.5,
            "В выборке не нашлось ни одной технологии",
            ha="center",
            va="center",
            color=INK_SECONDARY,
        )
        axes.set_axis_off()
        return figure

    # Перевёрнутая таблица: matplotlib рисует первый столбец снизу, а
    # лидер должен быть сверху.
    ordered = table.iloc[::-1]
    axes.barh(
        ordered["Технология"],
        ordered["Вакансий"],
        color=SERIES[0],
        height=0.62,
    )

    biggest = max(table["Вакансий"])
    for position, (_, row) in enumerate(ordered.iterrows()):
        if position < len(ordered) - LABELLED_BARS:
            continue
        axes.text(
            row["Вакансий"] + biggest * 0.015,
            position,
            f"{row['Вакансий']} ({percent(row['Доля, %'])})",
            va="center",
            fontsize=10,
            color=INK_SECONDARY,
        )

    axes.set_xlim(0, biggest * 1.22)
    axes.grid(axis="x", alpha=1.0, linewidth=0.8)
    axes.grid(axis="y", visible=False)
    axes.spines["bottom"].set_visible(False)
    return figure


def geography_chart(grouped: pd.DataFrame) -> plt.Figure:
    """Медиана зарплаты по группам городов: столбцы с подписями."""
    figure, axes = _figure(
        f"Медиана предложения «на руки» по группам городов (n = {int(grouped['Вакансий'].sum())})",
        "",
        "Медиана, ₽",
    )
    if grouped.empty:
        axes.text(
            0.5,
            0.5,
            "В выборке нет вакансий с зарплатой",
            ha="center",
            va="center",
            color=INK_SECONDARY,
        )
        axes.set_axis_off()
        return figure

    # Регионы — приглушены: в тексте речь именно о разрыве между столицей
    # и остальной страной, и цветом это подчёркивается.
    colors = [AXIS if name == "Регионы" else SERIES[0] for name in grouped["Группа"]]
    axes.bar(grouped["Группа"], grouped["Медиана, ₽"], color=colors, width=0.6)

    biggest = max(grouped["Медиана, ₽"])
    for position, row in grouped.iterrows():
        axes.text(
            position,
            row["Медиана, ₽"] + biggest * 0.03,
            f"{money(float(row['Медиана, ₽']))}\n{row['Вакансий']} вак.",
            ha="center",
            fontsize=10,
            color=INK_SECONDARY,
        )
    axes.set_ylim(0, biggest * 1.25)
    axes.tick_params(axis="x", rotation=15)
    # Числа стоят над столбцами, поэтому шкала Y только повторяла бы их.
    axes.set_yticklabels([])
    axes.grid(axis="y", visible=False)
    return figure


def experience_chart(table: pd.DataFrame, total: int) -> plt.Figure:
    """Две меры по уровню должности — двумя графиками, а не двумя осями.

    Медиана зарплаты и доля удалённой работы измеряются в разном, и совмещать
    их на одной картинке с двумя шкалами нельзя: оси подгоняются друг под
    друга произвольно, и глаз начинает видеть связь, которой в данных нет.
    """
    _style()
    figure, axes = plt.subplots(1, 2, figsize=FIGURE_SIZE)
    figure.patch.set_facecolor(SURFACE)
    figure.suptitle(
        f"Уровень должности: медиана «на руки» и удалённая работа (n = {total})",
        fontsize=15,
        color=INK,
        y=0.98,
    )

    left, right = axes
    plotted = table.dropna(subset=["Медиана, ₽"]) if not table.empty else table
    if plotted.empty:
        for axis in (left, right):
            axis.text(
                0.5,
                0.5,
                "Нет вакансий с зарплатой",
                ha="center",
                va="center",
                color=INK_SECONDARY,
            )
            axis.set_axis_off()
        return figure

    left.bar(plotted["Уровень"], plotted["Медиана, ₽"], color=SERIES[0], width=0.6)
    biggest = max(plotted["Медиана, ₽"])
    for position, row in plotted.iterrows():
        left.text(
            position,
            row["Медиана, ₽"] + biggest * 0.03,
            f"{money(float(row['Медиана, ₽']))}\n{row['Вакансий']} вак.",
            ha="center",
            fontsize=10,
            color=INK_SECONDARY,
        )
    left.set_ylim(0, biggest * 1.25)
    left.set_title("Медиана «на руки»")
    left.set_ylabel("₽")
    left.set_yticklabels([])
    left.grid(axis="y", visible=False)
    left.set_axisbelow(True)

    right.bar(table["Уровень"], table["Удалённо, %"], color=SERIES[1], width=0.6)
    for position, row in table.iterrows():
        right.text(
            position,
            row["Удалённо, %"] + 3,
            f"{percent(float(row['Удалённо, %']))}\n{row['Всего']} вак.",
            ha="center",
            fontsize=10,
            color=INK_SECONDARY,
        )
    right.set_ylim(0, 115)
    right.set_title("Доля удалённой работы")
    right.set_ylabel("%")
    right.set_yticklabels([])
    right.grid(axis="y", visible=False)
    right.set_axisbelow(True)

    figure.tight_layout()
    return figure


def _spread_labels(
    axes: plt.Axes,
    points: list[tuple[str, float, float]],
    minimum_gap_px: float = 15.0,
) -> list[tuple[str, float, float, float]]:
    """Разводит подписи, чтобы они не наезжали друг на друга.

    Возвращает для каждой точки: имя, координату X, настоящее значение Y и
    Y подписи. Если подпись сдвинулась, из точки к ней идёт тонкая
    линия-указатель: без неё подпись указывала бы на чужое значение.
    """
    figure = axes.get_figure()
    figure.canvas.draw()
    transformed = []
    for technology, x_value, y_value in points:
        display = axes.transData.transform((x_value, y_value))
        transformed.append([technology, x_value, y_value, display[1]])

    transformed.sort(key=lambda item: item[3])
    for index in range(1, len(transformed)):
        gap = transformed[index][3] - transformed[index - 1][3]
        if gap < minimum_gap_px:
            transformed[index][3] = transformed[index - 1][3] + minimum_gap_px

    result = []
    for technology, x_value, y_value, display_y in transformed:
        data_y = axes.transData.inverted().transform((0, display_y))[1]
        result.append((technology, x_value, y_value, data_y))
    return result


def monthly_trend_chart(months: pd.DataFrame, technologies: list[str]) -> plt.Figure:
    """Как менялась доля технологий по месяцам публикации.

    Линии подписаны у последней точки и продублированы легендой: подпись
    показывает, где линия закончилась, легенда — кто это.
    """
    figure, axes = _figure(
        "Доля вакансий с технологией по месяцам публикации",
        "Месяц",
        "Доля вакансий, %",
    )
    if months.empty or not technologies:
        axes.text(
            0.5,
            0.5,
            "Нет данных по месяцам",
            ha="center",
            va="center",
            color=INK_SECONDARY,
        )
        axes.set_axis_off()
        return figure

    positions = list(range(len(months)))
    plotted: list[tuple[str, float, float]] = []
    highest = 0.0
    for index, technology in enumerate(technologies):
        if technology not in months.columns:
            continue
        color = SERIES[index % len(SERIES)]
        values = months[technology].astype(float)
        axes.plot(
            positions,
            values,
            color=color,
            marker="o",
            markersize=8,
            linewidth=2,
            label=technology,
        )
        plotted.append((technology, float(positions[-1]), float(values.iloc[-1])))
        highest = max(highest, float(values.max()))

    axes.set_xticks(positions)
    axes.set_xticklabels(months["Месяц"])
    axes.set_xlim(-0.1, len(months) - 1 + 0.24)
    axes.set_ylim(0, max(highest * 1.12, 1))

    for technology, x_value, y_value, label_y in _spread_labels(axes, plotted):
        moved = abs(label_y - y_value) > 0.01
        axes.annotate(
            technology,
            xy=(x_value, y_value),
            xytext=(x_value + 0.02, label_y),
            textcoords="data",
            va="center",
            fontsize=9,
            color=INK_SECONDARY,
            arrowprops=({"arrowstyle": "-", "color": AXIS, "linewidth": 0.8} if moved else None),
        )

    # Легенда — под графиком: внутри она наезжала бы на линии.
    axes.legend(
        title="Технология",
        ncols=min(len(plotted), 5),
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
        labelcolor=INK_SECONDARY,
    )
    return figure
