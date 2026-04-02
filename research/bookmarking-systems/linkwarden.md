# Linkwarden

- Репозиторий: `https://github.com/linkwarden/linkwarden`
- Локальная ревизия: `815d2faa885bba5f715e80424155e3927a626ea6`
- Короткий вывод: у Linkwarden автоматизация завязана не на "категории", а на AI-тегирование. Теги одновременно выступают и обычными метками, и "правилами сохранения" для архивации/AI.

## 1. Как строятся и создаются теги

- Основная модель тега хранится в Prisma как `Tag` c уникальностью по паре `[name, ownerId]`.
- При ручном создании/редактировании тегов используется `upsert`: если тег с таким именем у пользователя уже есть, он обновляется; если нет, создаётся.
- При создании ссылки теги не нужно создавать заранее: `Link.create` использует `connectOrCreate`.
- При обновлении ссылки тоже используется `connectOrCreate`, а перед этим теги дедуплицируются по имени.
- У тега есть не только `name`, но и дополнительные флаги: `archiveAsScreenshot`, `archiveAsMonolith`, `archiveAsPDF`, `archiveAsReadable`, `archiveAsWaybackMachine`, `aiTag`, `aiGenerated`.

## 2. Как устроены языки

- UI работает через `next-i18next`.
- Поддерживаемые языки задаются централизованно в `next-i18next.config.js`.
- На SSR язык определяется так:
- если пользователь залогинен, берётся `user.locale`;
- иначе ищется лучший матч по `Accept-Language`.
- При сохранении профиля язык валидируется against списку разрешённых локалей.
- Переводы лежат в `apps/web/public/locales/<locale>/common.json`.
- Внутри переводов есть ключ `locale`; он используется не только для текста, но и для форматирования дат через `toLocaleString(...)`.

## 3. Как работает автоматическая категоризация / тегирование

- Явной автокатегоризации по коллекциям здесь нет. Коллекции ручные.
- Автоматизация есть именно для тегов.
- AI-тегирование запускается в worker-пайплайне во время `archiveHandler`, то есть после обработки и сохранения контента ссылки.
- Запуск происходит только если:
- у пользователя не `DISABLED` режим AI-tagging;
- для ссылки ещё не выставлен `aiTagged`;
- есть доступный AI-провайдер;
- глобально или через тег включён `aiTag`.
- Поддерживаются режимы:
- `GENERATE` — сгенерировать новые теги;
- `EXISTING` — выбрать из уже существующих пользовательских тегов;
- `PREDEFINED` — выбрать только из заранее заданного набора;
- `DISABLED` — ничего не делать.
- Для инференса берётся `metaDescription`, а если её нет, первые ~500 символов `textContent`.
- Промпты жёстко требуют JSON-массив, 3-5 тегов, максимум 2 слова, и указывают генерировать теги на языке исходного текста.
- В режиме `GENERATE` новые теги нормализуются в title case и режутся до 5 штук.
- Новые AI-теги создаются через `connectOrCreate`; если тег создаётся впервые, ему выставляется `aiGenerated: true`.

## 4. Смежные фичи, которые влияют на нашу подсистему

- В Linkwarden тег может быть не просто меткой, а носителем правил обработки.
- Через `aiTag` можно включать AI-тегирование выборочно по тегу.
- Через `archiveAs*` можно включать скриншоты/PDF/readable/monolith/Wayback тоже выборочно по тегу.
- В итоге архитектурный принцип такой: "тег = семантика + операционные правила".
- Есть отдельная опция `aiTagExistingLinks`, то есть система умеет дотягивать AI-теги не только для новых ссылок.

## 5. Принципы, которые можно забрать

- Не смешивать ручную привязку и инференс в одной точке UI: Linkwarden делает AI-тегирование в фоне, когда уже есть извлечённый контент.
- Хранить режим AI-тегирования как стратегию: reuse existing / predefined / generate.
- Дать тегам расширенную роль: обычная метка + триггер поведения пайплайна.
- Делать авто-тегирование идемпотентным через флаг вроде `aiTagged`.

## 6. Ключевые файлы

- Схема тегов и полей AI/locale: [packages/prisma/schema.prisma](../../external-research/linkwarden/packages/prisma/schema.prisma)
- Ручное создание/обновление тегов: [apps/web/lib/api/controllers/tags/createOrUpdateTags.ts](../../external-research/linkwarden/apps/web/lib/api/controllers/tags/createOrUpdateTags.ts)
- Создание ссылки с автосозданием тегов: [apps/web/lib/api/controllers/links/postLink.ts](../../external-research/linkwarden/apps/web/lib/api/controllers/links/postLink.ts)
- Обновление ссылки и `connectOrCreate` тегов: [apps/web/lib/api/controllers/links/linkId/updateLinkById.ts](../../external-research/linkwarden/apps/web/lib/api/controllers/links/linkId/updateLinkById.ts)
- AI-тегирование ссылки: [apps/worker/lib/autoTagLink.ts](../../external-research/linkwarden/apps/worker/lib/autoTagLink.ts)
- Промпты для AI-тегов: [apps/worker/lib/prompts.ts](../../external-research/linkwarden/apps/worker/lib/prompts.ts)
- Встраивание AI-тегирования в архивный pipeline: [apps/worker/lib/archiveHandler.ts](../../external-research/linkwarden/apps/worker/lib/archiveHandler.ts)
- UI настроек AI и режимов тегирования: [apps/web/pages/settings/preference.tsx](../../external-research/linkwarden/apps/web/pages/settings/preference.tsx)
- UI/состояние "теги как правила архивации": [apps/web/hooks/useArchivalTags.ts](../../external-research/linkwarden/apps/web/hooks/useArchivalTags.ts)
- Конфиг i18n: [apps/web/next-i18next.config.js](../../external-research/linkwarden/apps/web/next-i18next.config.js)
- SSR-выбор локали: [apps/web/lib/client/getServerSideProps.ts](../../external-research/linkwarden/apps/web/lib/client/getServerSideProps.ts)
- Сохранение пользовательской локали: [apps/web/lib/api/controllers/users/userId/updateUserById.ts](../../external-research/linkwarden/apps/web/lib/api/controllers/users/userId/updateUserById.ts)
- Переводы: [apps/web/public/locales/en/common.json](../../external-research/linkwarden/apps/web/public/locales/en/common.json)

