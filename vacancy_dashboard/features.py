"""Превращение текста вакансии в признаки: технологии, уровень, город, формат.

В hh.ru нет структурированных полей «стек» и «уровень должности» — есть
название, текст требований и список ключевых навыков, причём последний
почти всегда пустой. Поэтому и стек, и грейд приходится извлекать из текста.

Это честный, но шумный способ: он спотыкается о «Python-разработчик в
компании, где есть Go» и о вакансии, где грейд не назван. Все ограничения
перечислены в README, а доля вакансий, где признак удалось определить,
показывается рядом с каждым графиком.
"""

from __future__ import annotations

import re

from vacancy_dashboard import config

# ---------------------------------------------------------------------------
# Готовые регулярные выражения
# ---------------------------------------------------------------------------


def _alias_pattern(alias: str) -> str:
    """Регулярное выражение для одного написания технологии.

    Написание с префиксом «=» сравнивается регистрозависимо: так «Go» (язык)
    не совпадает с «go» (английский глагол в требованиях), а «1С» — с «1c».
    Границы слова не дают «sql» совпасть внутри «postgresql» и «rest» внутри
    «interest».
    """
    strict = alias.startswith("=")
    body = alias[1:] if strict else alias
    escaped = re.escape(body)
    prefix = r"(?<![A-Za-z0-9_])" if body[:1].isalnum() else ""
    suffix = r"(?![A-Za-z0-9_])" if body[-1:].isalnum() else ""
    flags = "(?-i:" if strict else "(?i:"
    return f"{flags}{prefix}{escaped}{suffix})"


def _build_technology_regex() -> tuple[re.Pattern[str], dict[str, str]]:
    """Одно регулярное выражение на все технологии и карта «группа → имя».

    Один проход по тексту вместо двухсот отдельных поисков: на выгрузке в
    несколько тысяч вакансий разница в секунды, а код остаётся простым.
    """
    alias_to_canonical: dict[str, str] = {}
    parts: list[str] = []
    for canonical, (_category, aliases) in config.TECHNOLOGIES.items():
        for alias in aliases:
            group = f"g{len(alias_to_canonical)}"
            alias_to_canonical[group] = canonical
            parts.append(f"(?P<{group}>{_alias_pattern(alias)})")
    # Длинные написания идут первыми: при совпадении в одной позиции
    # регулярное выражение выбирает первое подходящее.
    parts.sort(key=len, reverse=True)
    return re.compile("|".join(parts)), alias_to_canonical


TECHNOLOGY_PATTERN, _ALIAS_GROUPS = _build_technology_regex()


def _build_grade_regexes() -> tuple[tuple[str, re.Pattern[str]], ...]:
    patterns = []
    for grade, aliases in config.GRADE_PATTERNS:
        parts = [_alias_pattern(alias) for alias in aliases]
        patterns.append((grade, re.compile("|".join(parts))))
    return tuple(patterns)


GRADE_REGEXES = _build_grade_regexes()

# Неразрывный пробел. В HTML-описаниях hh.ru он встречается часто, а обычное
# разбиение на слова считает его обычным пробелом не всегда.
NBSP = "\u00a0"


# ---------------------------------------------------------------------------
# Публичные функции
# ---------------------------------------------------------------------------


def normalize_text(text: str | None) -> str:
    """Приводит текст к сравнимому виду.

    Неразрывные пробелы и переносы строк из HTML-описаний hh.ru мешают
    поиску, поэтому они заменяются обычными.
    """
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.replace(NBSP, " ")).strip()


def extract_technologies(text: str | None) -> list[str]:
    """Канонические названия технологий, встречающихся в тексте.

    Порядок результата не важен: он отсортирован по алфавиту, чтобы одни и те
    же вакансии всегда давали одинаковый набор.
    """
    if not text:
        return []
    found = {
        _ALIAS_GROUPS[match.lastgroup]
        for match in TECHNOLOGY_PATTERN.finditer(text)
        if match.lastgroup is not None
    }
    return sorted(found)


def extract_grade(text: str | None) -> str:
    """Уровень должности по названию вакансии.

    Если уровень не назван, возвращается `не указан`: молчать об этом
    опаснее, чем показать, сколько вакансий осталось без оценки.
    """
    if not text:
        return config.GRADE_UNKNOWN
    for grade, pattern in GRADE_REGEXES:
        if pattern.search(text):
            return grade
    return config.GRADE_UNKNOWN


def normalize_city(area_name: str | None) -> str:
    """Группирует город из поля `area` в одну из пяти.

    Пять групп — Москва, Петербург, остальные города-миллионники, регионы и
    удалённая работа. Внутри «регионов» разброс зарплат огромный, поэтому
    считать медиану по всей стране без такой группировки бессмысленно.
    """
    if not area_name:
        return config.REGION
    name = area_name.strip()
    lowered = name.lower()
    if "удалённ" in lowered or "удаленн" in lowered or "remote" in lowered:
        return config.REMOTE
    if name == config.MOSCOW:
        return config.MOSCOW
    if name == config.SAINT_PETERSBURG:
        return config.SAINT_PETERSBURG
    if name in config.REGIONS_OF_MILLIONS:
        return config.REGIONS_OF_MILLIONS[name]
    if name in config.MILLION_CITIES:
        return config.OTHER_MILLION
    return config.REGION


def normalize_work_format(work_format: list[str] | None) -> str:
    """Формат работы по полю `work_format`.

    hh.ru может указать несколько форматов сразу («офис или удалённо»).
    Тогда побеждает удалённый — он меняет всё остальное: в удалённой
    вакансии зарплату обычно не режут, а в офисной платят за место.
    """
    if not work_format:
        return "не указан"
    if "REMOTE" in work_format:
        return config.WORK_FORMATS["REMOTE"]
    if "HYBRID" in work_format:
        return config.WORK_FORMATS["HYBRID"]
    if "OFFICE" in work_format:
        return config.WORK_FORMATS["OFFICE"]
    return "не указан"


def technology_category(canonical: str) -> str:
    """Категория технологии по каноническому названию."""
    entry = config.TECHNOLOGIES.get(canonical)
    return entry[0] if entry else "Прочее"
