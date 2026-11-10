# Развёртывание дашборда

Документ описывает выкладку на VPS: Docker Compose, systemd и nginx.
Схема та же, что у `rest-api`, — одна и та же мысль про два проекта:
**приложение не публикует себя наружу само**, его выпускает nginx с
сертификатом, а systemd знает, как его поднять и перезапустить.

## Что должно быть на сервере

- Ubuntu 22.04 или новее;
- Docker Engine с плагином Compose (`docker compose`, не `docker-compose`);
- nginx и certbot;
- домен или поддомен для дашборда, например `dashboard.example.ru`.

## 1. Код и каталог данных

```bash
sudo git clone https://github.com/MeldanLess/vacancy-dashboard.git /opt/vacancy-dashboard
sudo mkdir -p /opt/vacancy-dashboard/data/raw
sudo chown -R 10001:10001 /opt/vacancy-dashboard/data/raw
```

Каталог `data/raw` принадлежит пользователю `10001` — под ним работает
контейнер, и таймер обновления пишет туда выгрузку.

## 2. Образ

Образ публикуется в GitHub Container Registry при отправке тега:

```bash
docker compose -f docker-compose.prod.yml pull
```

Если нужно собрать локально:

```bash
docker build -t vacancy-dashboard:latest .
```

## 3. Первая выгрузка

Дашборд без выгрузки показывает синтетическую фикстуру и честно
предупреждает об этом. Настоящие числа появляются после сбора:

```bash
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec -T dashboard \
    python -m vacancy_dashboard.collect --text python --pages 20 \
    --out data/raw/vacancies.json
```

Сбор занимает минуту и больше: API hh.ru отдаёт по 100 вакансий на
страницу, между страницами стоит пауза, а при 429 сборщик ждёт столько,
сколько просит сервер.

## 4. systemd

```bash
sudo cp deploy/vacancy-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now vacancy-dashboard
```

Юнит управляет compose-стеком: `systemctl reload vacancy-dashboard`
подтянет новый образ и перезапустит контейнер.

## 5. nginx и сертификат

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/vacancy-dashboard
sudo ln -s /etc/nginx/sites-available/vacancy-dashboard /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

В `deploy/nginx.conf` стоит заменить `dashboard.your-domain.com` на свой
домен — и в блоке с портом 80, и в блоке с HTTPS, и в путях к сертификату.

Сертификат:

```bash
sudo certbot --nginx -d dashboard.example.ru
```

Проверка, что всё живо:

```bash
curl -s https://dashboard.example.ru/_stcore/health
docker compose -f docker-compose.prod.yml ps
```

## 6. Ежедневное обновление выгрузки

```bash
sudo cp deploy/vacancy-dashboard-refresh.service /etc/systemd/system/
sudo cp deploy/vacancy-dashboard-refresh.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now vacancy-dashboard-refresh.timer
systemctl list-timers vacancy-dashboard-refresh.timer
```

Таймер запускает сборщик раз в сутки, в 06:17 утра. Дашборд читает файл
при каждом открытии страницы, поэтому новая выгрузка видна сразу, без
перезапуска контейнера.

Проверить, что обновление отрабатывает, можно вручную:

```bash
sudo systemctl start vacancy-dashboard-refresh.service
journalctl -u vacancy-dashboard-refresh.service -n 50
```

## Откат

Возвратиться на предыдущий образ — одна команда:

```bash
cd /opt/vacancy-dashboard
DASHBOARD_IMAGE=ghcr.io/meldanless/vacancy-dashboard:v1.0.0 \
    docker compose -f docker-compose.prod.yml up -d
```

Выгрузку при откате трогать не нужно: она лежит в каталоге `data/raw` и от
версии образа не зависит.

## Что здесь не сделано и почему

- **Бэкапов выгрузки нет.** Файл восстанавливается одной командой сбора, а
  хранение копий на том же сервере не даёт ничего: полезна копия на другом
  носителе, а это отдельная задача.
- **Авторизации нет.** Дашборд открыт всем — в нём обезличенные рыночные
  числа, а не данные конкретных работодателей. Если появится персональная
  выгрузка, доступ закрывается на уровне nginx.
- **Метрики не собираются.** У дашборда нет собственного `/metrics`;
  наблюдаемость сервера — на уровне nginx и Docker.
