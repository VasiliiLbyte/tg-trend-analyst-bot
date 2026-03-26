# tg-trend-analyst-bot

Telegram-бот на Python, который по расписанию собирает свежие бизнес‑тренды и тех‑прорывы (RSS + API), готовит аналитический пост (через Claude/OpenRouter) и публикует в Telegram‑канал.

## Требования

- Python 3.11+

## Быстрый старт (локально)

Установите зависимости:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Создайте `.env` на основе примера и заполните значения:

```bash
cp .env.example .env
```

Создайте конфиг источников:

```bash
cp sources.example.yaml sources.yaml
```

Запуск:

```bash
python -m app.main
```

## Переменные окружения

Смотрите `.env.example`. Секреты (токены/ключи) нельзя коммитить — храните только в `.env`.

## Команды качества (опционально)

```bash
ruff check .
black .
isort .
pytest
```
