# Команды проекта. Короткие имена для рутины, полные команды — в README.
#
#     make install   — поставить зависимости
#     make test      — прогнать тесты
#     make lint      — проверить стиль
#     make collect   — собрать вакансии с hh.ru
#     make pipeline  — посчитать ответы и построить графики
#     make notebooks — пересобрать ноутбуки из скрипта
#     make results   — подготовить раздел «Результаты» для README
#     make dump      — вся выгрузка целиком: сбор, расчёт, графики, README
#     make app       — запустить дашборд

PYTHON ?= python
PIP ?= $(PYTHON) -m pip
TEXT ?= python
PAGES ?= 20
INPUT ?= data/raw/vacancies.json

.PHONY: help install test coverage lint format check collect pipeline notebooks results dump app clean

help:
	@echo "install   — поставить зависимости (requirements.txt и requirements-dev.txt)"
	@echo "test      — прогнать тесты"
	@echo "coverage  — прогнать тесты и посчитать покрытие"
	@echo "lint      — проверить стиль (Ruff)"
	@echo "format    — переформатировать код (Ruff)"
	@echo "check     — стиль, тесты и пайплайн на фикстуре"
	@echo "collect   — собрать вакансии с hh.ru (нужна сеть)"
	@echo "pipeline  — посчитать три ответа и построить графики"
	@echo "notebooks — пересобрать ноутбуки из scripts/build_notebooks.py"
	@echo "results   — подготовить раздел «Результаты» для README из выгрузки"
	@echo "dump      — вся выгрузка целиком: сбор, расчёт, графики, README"
	@echo "app       — запустить дашборд на Streamlit"
	@echo "clean     — убрать временные файлы"

install:
	$(PIP) install -r requirements.txt -r requirements-dev.txt

test:
	$(PYTHON) -m pytest -q

coverage:
	$(PYTHON) -m pytest --cov=vacancy_dashboard --cov-report=term-missing

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

format:
	$(PYTHON) -m ruff format .

check: lint test
	$(PYTHON) -m vacancy_dashboard.pipeline --input tests/fixtures/vacancies_sample.json \
		--output-dir .ci/processed --figures-dir .ci/figures

collect:
	$(PYTHON) -m vacancy_dashboard.collect --text $(TEXT) --pages $(PAGES) --out $(INPUT)

pipeline:
	$(PYTHON) -m vacancy_dashboard.pipeline --input $(INPUT)

notebooks:
	$(PYTHON) scripts/build_notebooks.py

results:
	$(PYTHON) scripts/render_results.py --input $(INPUT) --text $(TEXT) --pages $(PAGES) \
		--write-readme README.md

# Весь путь до опубликованных чисел одной командой: собрать, посчитать,
# построить графики и вписать раздел в README.
dump: collect pipeline results

app:
	$(PYTHON) -m streamlit run app/dashboard.py

clean:
	rm -rf .pytest_cache .ruff_cache .coverage coverage.xml .nbout .ci
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
