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

Режимы запуска:

```bash
# Один dry-run цикл и выход (smoke)
python -m app.main --dry-run --once

# Только scheduler (без polling)
python -m app.main --scheduler-only
```

Полный пайплайн цикла:

`load_sources -> fetch -> normalize -> dedupe -> rank -> analyze -> compose -> publish`

## Переменные окружения

Смотрите `.env.example`. Секреты (токены/ключи) нельзя коммитить — храните только в `.env`.

Ключевые флаги:

- `DRY_RUN=true|false` - не публиковать в Telegram при `true`
- `FIRST_RUN_IMMEDIATELY=true|false` - запускать ли первый цикл сразу после старта
- `SCHEDULER_ONLY=true|false` - запускать только планировщик без aiogram polling

## Пример формата поста

```text
📊 Тренд-дайджест

🚀 1. AI startup raises funding
Источник: https://example.com/news-1

📈 2. Enterprise pricing shifts in cloud market
Источник: https://example.com/news-2

✅ Что делать дальше:
• Выберите 1 сигнал и проверьте гипотезу за 7 дней.
• Напишите, какой тренд разобрать глубже.
```

## Команды качества (опционально)

```bash
ruff check .
black .
isort .
pytest
```
