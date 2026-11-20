# RuStore Showcase API

Небольшой backend для MVP витрины приложений. Вся основная логика находится в `main.py`.

## Запуск

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Установка и запуск:

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

При первом запуске создаётся `rustore.db`, таблицы и несколько демонстрационных записей.

Документация API: http://127.0.0.1:8000/docs

## Эндпоинты

- `GET /api/v1/health`
- `GET /api/v1/categories`
- `GET /api/v1/apps?limit=20&offset=0`
- `GET /api/v1/apps?category=games`
- `GET /api/v1/apps/1`
- `GET /api/v1/apps/1/icon`
- `GET /api/v1/apps/1/apk`
- `GET /api/v1/apps/1/screenshots/0`

## Файлы

Положите файлы в `apps/{app_id}`:

- `apps/{app_id}/icon.png`
- `apps/{app_id}/screenshots/{screenshot_id}.png`
- `apps/{app_id}/release.apk`
