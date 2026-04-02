# Karakeep

- Репозиторий: `https://github.com/karakeep-app/karakeep`
- Локальная ревизия: `3a217a67a3f074ab315ed5bca3c07c054525ded5`
- Короткий вывод: это самый сильный референс под вашу подсистему. У Karakeep есть полноценный inference-pipeline, происхождение тега (`ai`/`human`), отдельный язык интерфейса и отдельный язык AI, curated tags и rule engine.

## 1. Как строятся и создаются теги

- Базовая нормализация имени тега делает только одно обязательное действие: убирает ведущие `#`, затем `.trim()`.
- Создание тега проходит через схемы `zod`, поэтому нормализация встроена уже на уровне валидации input.
- Тег создаётся как сущность пользователя с уникальностью внутри пользователя.
- При привязке тегов к bookmark можно передать либо `tagId`, либо `tagName`.
- Если тег с указанным именем ещё не существует, он создаётся автоматически перед attach.
- Связь bookmark <-> tag хранит отдельное поле `attachedBy`, то есть источник тега:
- `human`
- `ai`
- Это очень важный архитектурный момент: Karakeep разделяет сам объект тега и факт его прикрепления.
- Один и тот же тег может существовать как ручной и как AI-origin на разных bookmark relationships.

## 2. Как устроены языки

- Интерфейс использует `i18next` + `react-i18next`.
- Список UI-языков централизован в `supportedLangs`.
- Локаль интерфейса хранится отдельно в cookie-based local settings.
- Серверная и клиентская части читают один и тот же набор `./locales/<lang>/translation.json`.
- Параллельно с языком интерфейса есть отдельная настройка `inferredTagLang`.
- Это значит, что UI может быть, например, на русском, а AI-теги и summary можно генерировать на английском или любом другом языке.

## 3. Как работает автоматическая категоризация / тегирование

- Явной сущности "категория" здесь нет.
- Для категоризации используются теги, списки и rule engine.
- Главный AI-пайплайн живёт в worker `inference/tagging.ts`.
- Поддерживаются несколько типов источника контента:
- обычная ссылка;
- текстовая заметка;
- image asset;
- pdf asset.
- Для text inference система:
- достаёт plain text контент bookmark;
- строит prompt с учётом языка, custom prompts, tag style и curated tags;
- подрезает контент под token budget.
- Для image inference строится отдельный prompt и используется vision-capable model.
- Для pdf inference в prompt уходит уже извлечённый текст ассета.
- Ответ ожидается в structured JSON вида `{ "tags": [...] }`.
- После ответа:
- убираются ведущие `#`;
- старые AI-теги для bookmark удаляются;
- human-теги остаются нетронутыми;
- новые AI-теги матчятся по `normalizedName` к существующим;
- отсутствующие теги создаются;
- новые связи вставляются как `attachedBy: "ai"`.
- После attach/detach генерируются события `tagAdded` / `tagRemoved`, триггерятся reindex, webhook и rule engine.

## 4. Смежные фичи, которые влияют на нашу подсистему

- `tagStyle` позволяет задать финальный формат тегов:
- lowercase-hyphens
- lowercase-spaces
- lowercase-underscores
- titlecase-spaces
- titlecase-hyphens
- camelCase
- as-generated
- `curatedTagIds` ограничивают AI только заранее разрешённым словарём тегов.
- Пользователь может включать custom prompts для:
- всего tagging;
- только text tagging;
- только image tagging;
- summary.
- В custom prompts есть placeholder'ы `$tags`, `$aiTags`, `$userTags`.
- Есть preview фактического prompt прямо в UI.
- Есть глобальные env-настройки для моделей, контекста, timeout, structured/json/plain output, auto-tagging, auto-summarization.

## 5. Rule engine как соседняя система автоматической категоризации

- Rule engine умеет реагировать на события:
- `bookmarkAdded`
- `tagAdded`
- `tagRemoved`
- `addedToList`
- `removedFromList`
- `favourited`
- `archived`
- У правил есть условия по URL, title, feed source, bookmark type, bookmark source, наличию тега, архивности, favorite status.
- Действия правил:
- добавить тег;
- убрать тег;
- добавить в список;
- убрать из списка;
- скачать full page archive;
- пометить favourite;
- заархивировать.
- На практике это уже "автокатегоризация", просто не через отдельную таблицу категорий, а через теги и списки.

## 6. Принципы, которые можно забрать

- Разделять источник тега на уровне связи, а не только на уровне самого тега.
- Обновлять только AI-слой тегов, не затрагивая ручные теги пользователя.
- Развести язык интерфейса и язык инференса.
- Дать пользователю управлять стилем тега, словарём разрешённых тегов и custom prompts.
- Строить post-processing вокруг событий, чтобы tagging автоматически запускал последующие автоматизации.

## 7. Ключевые файлы

- Нормализация и типы тегов: [packages/shared/types/tags.ts](../../external-research/karakeep/packages/shared/types/tags.ts)
- Утилиты нормализации/стиля тегов: [packages/shared/utils/tag.ts](../../external-research/karakeep/packages/shared/utils/tag.ts)
- Prompt templates: [packages/shared/prompts.ts](../../external-research/karakeep/packages/shared/prompts.ts)
- Token-aware prompt builder: [packages/shared/prompts.server.ts](../../external-research/karakeep/packages/shared/prompts.server.ts)
- Env/config inference pipeline: [packages/shared/config.ts](../../external-research/karakeep/packages/shared/config.ts)
- Worker orchestration inference: [apps/workers/workers/inference/inferenceWorker.ts](../../external-research/karakeep/apps/workers/workers/inference/inferenceWorker.ts)
- Основной AI tagging pipeline: [apps/workers/workers/inference/tagging.ts](../../external-research/karakeep/apps/workers/workers/inference/tagging.ts)
- TRPC attach/detach тегов у bookmark: [packages/trpc/routers/bookmarks.ts](../../external-research/karakeep/packages/trpc/routers/bookmarks.ts)
- CRUD и статистика тегов: [packages/trpc/models/tags.ts](../../external-research/karakeep/packages/trpc/models/tags.ts)
- TRPC router для тегов: [packages/trpc/routers/tags.ts](../../external-research/karakeep/packages/trpc/routers/tags.ts)
- REST/OpenAPI слой тегов: [packages/api/routes/tags.ts](../../external-research/karakeep/packages/api/routes/tags.ts)
- Типы и схема rule engine: [packages/shared/types/rules.ts](../../external-research/karakeep/packages/shared/types/rules.ts)
- Модель rules: [packages/trpc/models/rules.ts](../../external-research/karakeep/packages/trpc/models/rules.ts)
- Исполнение rule engine: [packages/trpc/lib/ruleEngine.ts](../../external-research/karakeep/packages/trpc/lib/ruleEngine.ts)
- UI AI-настроек: [apps/web/components/settings/AISettings.tsx](../../external-research/karakeep/apps/web/components/settings/AISettings.tsx)
- Серверный i18n: [apps/web/lib/i18n/server.ts](../../external-research/karakeep/apps/web/lib/i18n/server.ts)
- Клиентский i18n: [apps/web/lib/i18n/client.ts](../../external-research/karakeep/apps/web/lib/i18n/client.ts)
- Список UI-языков: [packages/shared/langs.ts](../../external-research/karakeep/packages/shared/langs.ts)
- Локальные настройки пользователя и язык интерфейса: [apps/web/lib/userLocalSettings/userLocalSettings.ts](../../external-research/karakeep/apps/web/lib/userLocalSettings/userLocalSettings.ts)
- Документация по automation/rules: [docs/docs/04-using-karakeep/advanced-workflows.md](../../external-research/karakeep/docs/docs/04-using-karakeep/advanced-workflows.md)

