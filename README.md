# Tagging Subsystem MVP

Автономный сервис для автоматизированного тегирования и категоризации избранного контента.

Сервис:

- принимает текст и метаданные документа;
- создаёт асинхронную задачу обработки;
- определяет одну основную категорию;
- извлекает набор тегов;
- сохраняет статусы и результат в БД;
- может опционально усиливать результат через внешний `LLM/API`.

## Local Run

### 1. Prepare environment

```bash
uv sync
cp .env.example .env
```

По умолчанию сервис ожидает `PostgreSQL`:

```env
TAGGING_DATABASE_URL=postgresql+psycopg://tagging:tagging@localhost:5432/tagging
```

Для локального smoke-run допустим и `SQLite`:

```env
TAGGING_DATABASE_URL=sqlite:///./tagging.db
```

### 2. Start the API

```bash
uv run uvicorn nir_tagging_service.app:app --host 0.0.0.0 --port 8000 --reload
```

После старта Swagger UI доступен по адресу `http://127.0.0.1:8000/api/v1/tagging/docs`.
OpenAPI schema доступна по адресу `http://127.0.0.1:8000/api/v1/tagging/openapi.json`.

При первом реальном inference `sentence-transformers` модель загрузится из Hugging Face.

### 3. Health And Readiness

Сервис отдаёт два базовых технических endpoint:

- `GET /health` для liveness-проверки;
- `GET /readiness` для проверки, что API, database layer и pipeline services инициализированы.

## Docker Dev Run

### 1. Prepare environment

```bash
cp .env.example .env
docker compose up --build
```

Docker поднимает `api` и `db`, а API становится доступен по адресу `http://127.0.0.1:8000`.
Swagger UI в Docker-сценарии доступен по адресу `http://127.0.0.1:8000/api/v1/tagging/docs`.

На первом старте контейнер синхронизирует Python dependencies через `uv sync`, а при первом реальном inference скачает модель `sentence-transformers`, поэтому cold start будет заметно дольше обычного.

### 2. Stop the environment

```bash
docker compose down
```

### 3. Rebuild after dependency changes

Если вы меняли `pyproject.toml` или хотите полностью пересобрать dev-образ, выполните:

```bash
docker compose up --build
```

Исходный локальный сценарий через `uv` остаётся рабочим и подходит, если Docker не нужен.

## Example Request

```bash
curl -X POST http://127.0.0.1:8000/api/v1/tagging/jobs \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "Transformer embeddings improve semantic search quality and keyphrase extraction makes results easier to explain.",
    "source": "article",
    "metadata": {"title": "Embeddings for semantic search", "language": "en"},
    "options": {"max_tags": 5, "use_llm_postprocess": false}
  }'
```

Ожидаемый ответ:

```json
{
  "job_id": "3f781ab1-74fc-4704-95e8-b89adba13a11",
  "status": "queued",
  "document_id": "749cc4c8-f34b-46a5-b478-40d8b2390e6b",
  "status_url": "/api/v1/tagging/jobs/3f781ab1-74fc-4704-95e8-b89adba13a11",
  "result_url": "/api/v1/tagging/jobs/3f781ab1-74fc-4704-95e8-b89adba13a11/result"
}
```

Далее:

```bash
curl http://127.0.0.1:8000/api/v1/tagging/jobs/<job_id>
curl http://127.0.0.1:8000/api/v1/tagging/jobs/<job_id>/result
```

## Example Texts

В `examples/` есть несколько типов примеров для ручной проверки и baseline-оценки:

- `quality-evaluation-dataset.json` для category benchmark и базовых demo-кейсов;
- `tag-quality-evaluation-dataset.json` для проверки качества тегов;
- `long-document-evaluation-dataset.json` для long-document classification;
- `source-material-examples.json` для дополнительных ручных примеров, собранных из преобразованных фрагментов документов и README/tutorial-подобных текстов.

Для длинных и громоздких кейсов JSON может ссылаться на обычные `.txt` файлы через относительный `file_path`. Такие тексты лежат в `examples/long-documents/` и `examples/source-materials/`, поэтому их можно редактировать отдельно от JSON-метаданных.

## MVP Scope

В MVP вошло:

- автономный `FastAPI` сервис;
- хранение `documents`, `tagging_jobs`, `tagging_results`;
- базовая предобработка текста;
- категоризация через `sentence-transformers` + cosine similarity;
- тегирование через `KeyBERT` с нормализацией и фильтрами;
- асинхронный background pipeline;
- evaluation dataset и demo artifacts;
- optional `LLM/API` enhancer как строго opt-in слой.

[//]: # ()
[//]: # (Оставлено на следующий этап:)

[//]: # ()
[//]: # (- более умная фильтрация шумовых тегов на длинных русскоязычных документах;)

[//]: # (- более точная калибровка научных long-document кейсов;)

[//]: # (- durable queue вместо `BackgroundTasks`;)

[//]: # (- миграции и полноценный deployment stack;)

[//]: # (- количественная оценка на большей размеченной выборке.)

## Known Limitations

- на смешанных RU/EN long-document кейсах точность всё ещё сильнее зависит от качества category catalog и phrasing в тексте, чем на коротких заметках;
- `KeyBERT` иногда отдаёт extractive-фразы, которые остаются лишь частично очищенными;
- background processing не переживает restart процесса;
- OCR, мультимодальность и vector store не входят в MVP;
- optional `LLM/API` режим зависит от внешнего провайдера, latency и token-cost.
