# Tagging Subsystem MVP

Автономный сервис для автоматизированного тегирования и категоризации избранного контента.

Сервис:

- принимает текст и метаданные документа;
- создаёт асинхронную задачу обработки;
- определяет одну основную категорию;
- извлекает набор тегов;
- сохраняет статусы и результат в БД;
- может опционально усиливать результат через внешний `LLM/API`.

Ключевая идея MVP: базовый результат строится локально и воспроизводимо через
`sentence-transformers` + rule hints + `KeyBERT`, а внешний `LLM/API` остаётся
строго опциональным постпроцессингом для уточнения тегов и объяснения.

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
Если локальный snapshot уже есть в кэше Hugging Face, сервис и benchmark-скрипты
используют его без повторного сетевого запроса.

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

## Docker Production Run

Для production-сценария используется отдельный [Dockerfile](/Users/vkh/PycharmProjects/NIR/Dockerfile)
и [compose.prod.yaml](/Users/vkh/PycharmProjects/NIR/compose.prod.yaml). В отличие от dev-контура,
production-образ:

- не использует bind mounts;
- не включает `--reload`;
- устанавливает только runtime-зависимости;
- содержит встроенный `HEALTHCHECK`.

### 1. Local Production Build

```bash
docker compose -f compose.prod.yaml build api
```

### 2. Local Production Run With PostgreSQL

```bash
docker compose -f compose.prod.yaml up --build
```

### 3. Smoke Run From Published Image

После публикации можно запустить образ и без внешней БД через `SQLite`:

```bash
docker run --rm -p 8000:8000 \
  -e TAGGING_DATABASE_URL=sqlite:///./tagging.db \
  ghcr.io/bezura/nir:latest
```

## Container CD To GHCR

Публикация Docker-образа встроена во второй job основного workflow
[ci-cd.yml](/Users/vkh/PycharmProjects/NIR/.github/workflows/ci-cd.yml).
Она срабатывает только по `git tag` вида `v*` и только после успешного
завершения job с backend-тестами.

### Release Trigger

```bash
git tag v0.1.0
git push origin v0.1.0
```

После этого GitHub Actions:

- сначала выполняет backend `CI`;
- собирает production-образ из `Dockerfile`;
- публикует его в GitHub Container Registry;
- выставляет теги `v0.1.0`, `0.1.0` и `latest`.

Для текущего репозитория образ публикуется в:

```text
ghcr.io/bezura/nir
```

### Pull Published Image

```bash
docker pull ghcr.io/bezura/nir:latest
```

Таким образом, в репозитории настроены:

- `CI`: автоматический прогон тестов;
- `CD`: автоматическая сборка и публикация Docker-контейнера по release-tag.

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

## Architecture And Pipeline

Основной pipeline состоит из пяти этапов:

1. `preprocessing`:
   нормализация текста, языка, title и формирование чанков отдельно для
   категоризации и тегирования;
2. `categorization`:
   вычисление embeddings через
   `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`,
   сравнение с каталогом категорий по cosine similarity и применение rule hints;
3. `tag_extraction`:
   извлечение кандидатов через `KeyBERT`, очистка, нормализация,
   дедупликация и согласование с категорией;
4. `llm_postprocess`:
   опциональный вызов внешнего OpenAI-compatible API для уточнения тегов и
   генерации краткого explanation;
5. `persistence`:
   сохранение `documents`, `tagging_jobs`, `tagging_results` и прогресса job в БД.

Фактически это гибридный pipeline: локальная модель отвечает за воспроизводимый
baseline, а внешний LLM используется только как opt-in слой, не блокирующий
основной сценарий.

## Repository Structure

Ключевые backend-модули:

- `nir_tagging_service/app.py` и `nir_tagging_service/api/`:
  FastAPI-приложение и HTTP endpoints;
- `nir_tagging_service/pipeline.py`:
  оркестрация асинхронной обработки job;
- `nir_tagging_service/preprocessing.py`:
  подготовка текста и формирование чанков;
- `nir_tagging_service/categorization.py` и `nir_tagging_service/category_catalog.py`:
  таксономия категорий и модель категоризации;
- `nir_tagging_service/tag_extraction.py`:
  извлечение, фильтрация и нормализация тегов;
- `nir_tagging_service/llm_enhancement.py`:
  optional LLM postprocess;
- `nir_tagging_service/evaluation.py`:
  воспроизводимые benchmark-проверки.

Публичные функции и классы в основных backend-модулях снабжены type hints и
docstrings; в нетривиальных местах добавлены краткие комментарии по логике
pipeline.

## Reproducibility And Verification

### Local Checks

Полный локальный прогон тестов:

```bash
uv run pytest -q
```

Встроенный benchmark для категорий, long-document кейсов и качества тегов:

```bash
uv run python -m nir_tagging_service.evaluation
```

Сервис запускается как на `PostgreSQL`, так и в локальном smoke-сценарии на
`SQLite`, поэтому проект воспроизводим на чистой машине без отдельной ручной
настройки БД для первого запуска.

### CI

Для репозитория настроен GitHub Actions workflow
`.github/workflows/ci-cd.yml`. Он выполняет:

- checkout репозитория;
- установку `Python 3.13` и `uv`;
- `uv sync --all-groups`;
- `uv run pytest -q` на `SQLite`.

При push тега `v*` этот же workflow дополнительно запускает job `Docker Publish`,
но только после успешного завершения `backend-tests`.

Это обеспечивает базовую проверку, что backend-код запускается и тесты проходят
в чистом окружении, а release-контейнер публикуется только после успешного `CI`.

### Benchmark Snapshot

Ниже приведён пример первичного benchmark-отчёта для встроенных датасетов:

```json
{
  "categories": {
    "category_accuracy": 0.6666666666666666,
    "domain_accuracy": 0.8888888888888888,
    "exact_leaf_accuracy": 0.6666666666666666,
    "long_document_accuracy": 0.0,
    "low_confidence_accuracy": 0.0,
    "low_confidence_rate": 0.3333333333333333,
    "path_prefix_accuracy": 0.8888888888888888,
    "short_document_accuracy": 1.0,
    "top_2_accuracy": 0.6666666666666666,
    "total_cases": 9
  },
  "long_documents": {
    "domain_accuracy": 0.25,
    "exact_leaf_accuracy": 0.0,
    "expected_low_confidence_match_rate": 0.25,
    "long_document_accuracy": 0.0,
    "low_confidence_accuracy": 0.0,
    "low_confidence_rate": 1.0,
    "path_prefix_accuracy": 0.25,
    "top_2_accuracy": 0.0,
    "total_cases": 4
  },
  "tags": {
    "average_expected_matches": 1.0,
    "precision_at_5": 0.2,
    "total_cases": 6
  }
}
```

Интерпретация для MVP:

- short-document categorization уже работает стабильно;
- long-document сценарии остаются главным слабым местом текущего baseline и
  требуют дополнительной калибровки каталога, chunk selection и правил(возможно требуется редактирование пайплайна тестирования);
- tag benchmark показывает рабочую baseline-экстракцию, пригодную для развития
  каталога и правил.

## Model And LLM Pipeline

### Local Transformer Backbone

Для категоризации используется локальная модель
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.

- роль в системе: multilingual sentence embeddings для сравнения документа с
  таксономией категорий;
- модель загружается локально и используется как embedding-backbone внутри
  categorization pipeline;
- отдельное обучение собственной нейронной сети в рамках проекта не требуется.

### Optional External LLM Stage

Опциональный postprocess настраивается через переменные окружения:

- `TAGGING_OPENAI_BASE_URL`;
- `TAGGING_OPENAI_API_KEY`;
- `TAGGING_OPENAI_PROJECT`;
- `TAGGING_OPENAI_MODEL`;
- `TAGGING_OPENAI_TIMEOUT_SECONDS`.

Если `use_llm_postprocess=false` или API не настроен, сервис полностью работает
в локальном deterministic-режиме без внешнего LLM. Если `use_llm_postprocess=true`,
внешняя модель используется только для уточнения уже найденных тегов и генерации
краткого explanation, а не для замены базовой категоризации.

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
