# Briefkasten

- Репозиторий: `https://github.com/ndom91/briefkasten`
- Локальная ревизия: `1ac842944b289eb93f1f56f920e69dfcc17917da`
- Короткий вывод: в этом проекте есть отдельные ручные сущности `Category` и `Tag`, но автоматического тегирования/категоризации нет. Из автоматизации здесь полезно смотреть только metadata extraction при добавлении bookmark.

## 1. Как строятся и создаются теги

- В Prisma есть отдельная модель `Tag` и отдельная join-таблица `TagsOnBookmarks`.
- У тега уникальность по паре `[name, userId]`.
- В `POST/PUT /api/bookmarks` теги можно передать массивом строк.
- Для каждого тега выполняется `prisma.tag.upsert(...)`.
- Затем создаются связи в `tagsOnBookmarks` тоже через `upsert`.
- Итог: тег можно не создавать заранее вручную, он появится в момент сохранения bookmark.
- Параллельно есть отдельный ручной CRUD endpoint `/api/tags`.
- В теге есть дополнительное поле `emoji`, то есть UI использует не только текстовое имя.

## 2. Как строятся и создаются категории

- Категории здесь отдельная first-class сущность `Category`, а не просто saved filter.
- У категории тоже уникальность `[name, userId]`.
- Но в `POST/PUT /api/bookmarks` категория НЕ создаётся автоматически.
- Bookmark API делает только `connect` по `name_userId`.
- Значит категория должна существовать заранее, иначе connect не сработает.
- Для категорий есть отдельный ручной CRUD endpoint `/api/categories`.

## 3. Как устроены языки

- Полноценной i18n-подсистемы нет.
- Не используется `i18next`, `next-intl` или аналогичная библиотека переводов.
- UI-тексты в основном хардкожены.
- Единственное заметное использование языка браузера: на клиенте читается `navigator.languages / navigator.language`, и это значение кладётся в `settings.locale`.
- Затем `settings.locale` используется для `toLocaleString(...)` / `toLocaleDateString(...)`, то есть в основном для форматирования даты/времени.
- Практически это не мультиязычность интерфейса, а только locale-aware formatting.

## 4. Как работает автоматическая категоризация / тегирование

- Никак: в репозитории нет AI, rule engine, classifier, embedding-пайплайна или DSL-автотегов.
- Категории и теги здесь полностью ручные.
- Единственная автоматизация, связанная с bookmark enrichment:
- при `POST /api/bookmarks` страница фетчится;
- `metascraper` достаёт `title` и `description`;
- если пользователь не передал свои значения, они подставляются автоматически.
- То есть система умеет автообогащать metadata, но не умеет на её основе назначать теги или категории.

## 5. Смежные фичи, которые влияют на нашу подсистему

- Важно различать две стратегии:
- теги автосоздаются при bookmark save;
- категории не автосоздаются и должны жить отдельно.
- Это может быть полезным reference, если вы хотите жёстко разделить "свободные метки" и "контролируемый словарь категорий".
- В импорте есть следы TODO вокруг тегов, то есть автоматизация импорта тегов здесь явно не является зрелой частью системы.

## 6. Принципы, которые можно забрать

- Если категории должны быть контролируемым словарём, их лучше не auto-create из пользовательского ввода.
- Если теги нужны как лёгкие свободные метки, их удобно auto-upsert'ить прямо в bookmark API.
- Metadata extraction можно оставить отдельным, независимым шагом перед будущим classifier/tagger.

## 7. Ключевые файлы

- Prisma schema для bookmark/tag/category: [prisma/schema.prisma](../../external-research/briefkasten/prisma/schema.prisma)
- Bookmark API с upsert тегов и connect категории: [src/pages/api/bookmarks/index.js](../../external-research/briefkasten/src/pages/api/bookmarks/index.js)
- CRUD тегов: [src/pages/api/tags/index.js](../../external-research/briefkasten/src/pages/api/tags/index.js)
- CRUD категорий: [src/pages/api/categories/index.js](../../external-research/briefkasten/src/pages/api/categories/index.js)
- Детект locale браузера: [src/pages/index.jsx](../../external-research/briefkasten/src/pages/index.jsx)
- Zustand store с `locale`: [src/lib/store.js](../../external-research/briefkasten/src/lib/store.js)
- UI быстрого добавления bookmark и ручного выбора тегов/категорий: [src/components/quick-add.jsx](../../external-research/briefkasten/src/components/quick-add.jsx)
- UI редактирования bookmark: [src/components/slide-out.jsx](../../external-research/briefkasten/src/components/slide-out.jsx)
- README с общей функциональностью, включая metadata extraction: [README.md](../../external-research/briefkasten/README.md)
