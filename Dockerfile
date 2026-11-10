# syntax=docker/dockerfile:1

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Сначала зависимости: этот слой кэшируется и пересобирается только при
# изменении requirements.txt, а не при каждой правке исходников.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY vacancy_dashboard ./vacancy_dashboard
COPY app ./app
COPY scripts ./scripts

# Каталог с выгрузкой создаём заранее: он подключается снаружи, и без него
# контейнер стартует не с той точки монтирования.
RUN mkdir -p /app/data/raw \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app

# Приложение не от root: ошибка в коде не должна давать root внутри
# контейнера.
USER appuser

EXPOSE 8501

# У Streamlit есть страница проверки состояния — ею и меряем живость
# сервиса, не открывая приложение.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health')" || exit 1

# `--server.headless=true` — контейнеру не нужен браузер, а `--browser.gatherUsageStats=false`
# убирает запросы к внешним сервисам, о которых стоит помнить при выкладке.
CMD ["streamlit", "run", "app/dashboard.py", \
     "--server.address=0.0.0.0", "--server.port=8501", \
     "--server.headless=true", "--browser.gatherUsageStats=false"]
