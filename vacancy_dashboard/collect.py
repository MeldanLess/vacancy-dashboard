"""Сбор вакансий через открытый API hh.ru.

API hh.ru не требует регистрации для чтения: достаточно указать
`User-Agent` с именем приложения и контактным адресом. С токеном
(`Authorization: Bearer …`) отдаётся больше результатов и выше лимит, но
сборщик работает и без него.

Что важно в этом модуле:

* **пагинация** — вакансии приходят по 100 штук на страницу, и их нужно
  донести до конца;
* **вежливость** — между запросами стоит пауза, а на 429 приложение ждёт
  столько, сколько просит сервер, и только потом повторяет;
* **проверка User-Agent** — без него hh.ru отвечает 403, и это самая
  частая причина «пустой» выгрузки.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

from vacancy_dashboard import config

# Сколько раз повторить запрос, прежде чем сдаться.
MAX_ATTEMPTS = 4

# Пауза между попытками растёт: 1 с, 2 с, 4 с, 8 с.
BACKOFF_SECONDS = 1.0


@dataclass(frozen=True)
class CollectSettings:
    """Настройки одного прохода сбора."""

    text: str = "python"
    area: int = config.AREA_RUSSIA
    max_pages: int = config.DEFAULT_MAX_PAGES
    per_page: int = 100
    delay: float = config.DEFAULT_DELAY_SECONDS
    only_with_salary: bool = False
    order_by: str = "publication_time"
    period_days: int | None = None
    token: str | None = None
    user_agent: str = config.DEFAULT_USER_AGENT
    timeout: float = 30.0
    extra: dict[str, Any] = field(default_factory=dict)

    def params(self, page: int) -> dict[str, Any]:
        """Параметры запроса для одной страницы."""
        params: dict[str, Any] = {
            "text": self.text,
            "area": self.area,
            "page": page,
            "per_page": min(self.per_page, 100),
            "order_by": self.order_by,
        }
        if self.only_with_salary:
            params["only_with_salary"] = "true"
        if self.period_days:
            params["period"] = self.period_days
        params.update(self.extra)
        return params

    def headers(self) -> dict[str, str]:
        """Заголовки запроса.

        hh.ru отклоняет запросы без `User-Agent`: считается, что иначе
        скрипт может завалить сайт. Имя приложения и контактный адрес в
        `User-Agent` — это условие, а не формальность.
        """
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers


class CollectError(RuntimeError):
    """Сбор не удался: сервер не отвечает или отвечает отказом."""


def fetch_page(
    session: requests.Session,
    settings: CollectSettings,
    page: int,
) -> dict[str, Any]:
    """Одна страница результатов с повторами при сбое.

    При 429 сервер сам говорит, сколько ждать, — этим и пользуемся. Остальные
    ошибки повторяем с удваивающейся паузой.
    """
    last_error: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = session.get(
                config.API_URL,
                params=settings.params(page),
                headers=settings.headers(),
                timeout=settings.timeout,
            )
        except requests.RequestException as error:
            last_error = error
        else:
            if response.status_code == 200:
                return response.json()
            if response.status_code == 429:
                wait = float(response.headers.get("Retry-After", BACKOFF_SECONDS * (2**attempt)))
                time.sleep(wait)
                last_error = CollectError("hh.ru попросил подождать (429)")
                continue
            if response.status_code >= 500:
                last_error = CollectError(f"hh.ru ответил {response.status_code}")
            else:
                raise CollectError(
                    f"hh.ru ответил {response.status_code} на страницу {page}: "
                    f"{response.text[:300]}"
                )
        time.sleep(BACKOFF_SECONDS * (2**attempt))

    raise CollectError(f"не удалось получить страницу {page}: {last_error}")


def collect(settings: CollectSettings) -> list[dict[str, Any]]:
    """Собирает вакансии постранично и возвращает их списком."""
    vacancies: list[dict[str, Any]] = []
    with requests.Session() as session:
        for page in range(settings.max_pages):
            payload = fetch_page(session, settings, page)
            items = payload.get("items") or []
            if not items:
                break
            vacancies.extend(items)
            pages = payload.get("pages")
            if pages is not None and page + 1 >= pages:
                break
            if page + 1 < settings.max_pages:
                time.sleep(settings.delay)
    return vacancies


def save(vacancies: list[dict[str, Any]], path: str | Path) -> Path:
    """Складывает сырые вакансии в JSON-файл."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(vacancies, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    return target


def load(path: str | Path) -> list[dict[str, Any]]:
    """Читает сырые вакансии из JSON-файла."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def settings_from_env(**overrides: Any) -> CollectSettings:
    """Настройки сбора с учётом переменных окружения.

    `HH_TOKEN` — необязательный токен приложения hh.ru. Без него сборщик
    работает, но отдаёт меньше результатов.
    """
    token = os.environ.get("HH_TOKEN") or None
    user_agent = os.environ.get("HH_USER_AGENT") or config.DEFAULT_USER_AGENT
    base: dict[str, Any] = {"token": token, "user_agent": user_agent}
    base.update(overrides)
    return CollectSettings(**base)


def main(argv: list[str] | None = None) -> int:
    """Точка входа: `python -m vacancy_dashboard.collect …`."""
    parser = argparse.ArgumentParser(description="Собрать вакансии из API hh.ru.")
    parser.add_argument("--text", default="python", help="Поисковый запрос.")
    parser.add_argument("--area", type=int, default=config.AREA_RUSSIA, help="Код региона.")
    parser.add_argument(
        "--pages", type=int, default=config.DEFAULT_MAX_PAGES, help="Сколько страниц."
    )
    parser.add_argument("--per-page", type=int, default=100, help="Вакансий на страницу.")
    parser.add_argument(
        "--delay",
        type=float,
        default=config.DEFAULT_DELAY_SECONDS,
        help="Пауза между запросами, с.",
    )
    parser.add_argument("--period", type=int, default=None, help="Только за последние N дней.")
    parser.add_argument(
        "--only-with-salary",
        action="store_true",
        help="Оставить только вакансии с указанной зарплатой.",
    )
    parser.add_argument(
        "--out",
        default="data/raw/vacancies.json",
        help="Куда сложить сырой JSON.",
    )
    args = parser.parse_args(argv)

    settings = settings_from_env(
        text=args.text,
        area=args.area,
        max_pages=args.pages,
        per_page=args.per_page,
        delay=args.delay,
        period_days=args.period,
        only_with_salary=args.only_with_salary,
    )
    vacancies = collect(settings)
    target = save(vacancies, args.out)
    print(f"Собрано вакансий: {len(vacancies)} → {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
