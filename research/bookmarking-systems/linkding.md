# Linkding

- Репозиторий: `https://github.com/sissbruecker/linkding`
- Локальная ревизия: `573b6f5411eaaa18ccc9524544fa27bb594c532b`
- Короткий вывод: это rule-based reference без AI. Теги здесь простые, а автотегирование построено на пользовательском DSL по URL-правилам. Отдельной сущности категорий нет.

## 1. Как строятся и создаются теги

- Тег хранится как простая Django-модель `Tag(name, date_added, owner)`.
- На входе теги разбираются через `parse_tag_string`.
- Нормализация очень простая:
- trim;
- внутренние пробелы заменяются на `-`;
- пустые теги удаляются;
- дубликаты убираются case-insensitive;
- результат сортируется case-insensitive.
- При сохранении bookmark система вызывает `get_or_create_tags`.
- `get_or_create_tag` ищет тег по `name__iexact`, то есть уникальность фактически регистронезависимая.
- Если тег не найден, он создаётся автоматически.
- Есть отдельный ручной CRUD для тегов и отдельный merge flow, где несколько тегов объединяются в один.

## 2. Как устроены языки

- Базовая инфраструктура i18n у проекта есть, потому что используется Django `LocaleMiddleware`.
- В `settings/base.py` включены `USE_I18N = True` и `LANGUAGE_CODE = "en-us"`.
- Но по исходникам видно, что реальная многоязычность тут почти не развита:
- в коде почти нет `gettext`/`trans`;
- есть единичное использование `gettext_lazy`;
- есть шаблон, который наоборот форсирует ошибки в английский через `{% language 'en-us' %}`;
- каталогов переводов `.po/.mo` в репозитории нет.
- Практический вывод: архитектурный хук под i18n есть, но продукт сейчас по сути англоязычный.

## 3. Как работает автоматическая категоризация / тегирование

- LLM/AI/ML-подсистемы здесь нет.
- Автоматизация реализована как набор пользовательских правил в поле `user.profile.auto_tagging_rules`.
- Эти правила парсятся функцией `auto_tagging.get_tags(script, url)`.
- Формат очень простой: одна строка = `<url-pattern> <tag1> <tag2> ...`.
- Система умеет матчить:
- домен;
- path prefix;
- query string subset;
- fragment prefix.
- Есть поддержка IDN-доменов через `idna`.
- Пустые строки и комментарии игнорируются.
- На bookmark save логика такая:
- пользовательские ручные теги разбираются;
- если есть `auto_tagging_rules`, вычисляются авто-теги по URL;
- авто-теги добавляются к ручным, если их ещё нет;
- итоговый набор тегов полностью устанавливается на bookmark.

## 4. Смежные фичи, которые влияют на нашу подсистему

- Отдельной сущности "категория" нет.
- Ближайший аналог категоризации здесь это `bundles`.
- `bundles` не классифицируют bookmark при сохранении, а задают сохранённые фильтры:
- search;
- any_tags;
- all_tags;
- excluded_tags;
- unread/shared filters.
- То есть bundles полезны как reference для "виртуальных категорий", но не для auto-classification pipeline.

## 5. Принципы, которые можно забрать

- Если нужна дешёвая и полностью детерминированная автотеговка, DSL по URL-паттернам работает очень просто и предсказуемо.
- Полезно добавлять авто-теги не вместо ручных, а поверх ручных.
- Стоит держать авто-правила на уровне профиля пользователя, если логика сильно персонализированная.
- Для поиска и "категорий без категорий" можно использовать сохранённые фильтры вроде bundles.

## 6. Ключевые файлы

- Модель тега и разбор строки тегов: [bookmarks/models.py](../../external-research/linkding/bookmarks/models.py)
- Создание/поиск тегов: [bookmarks/services/tags.py](../../external-research/linkding/bookmarks/services/tags.py)
- Bookmark service и объединение ручных/авто-тегов: [bookmarks/services/bookmarks.py](../../external-research/linkding/bookmarks/services/bookmarks.py)
- Rule-based auto-tagging DSL: [bookmarks/services/auto_tagging.py](../../external-research/linkding/bookmarks/services/auto_tagging.py)
- Тесты auto-tagging правил: [bookmarks/tests/test_auto_tagging.py](../../external-research/linkding/bookmarks/tests/test_auto_tagging.py)
- API serializer с `tag_names`: [bookmarks/api/serializers.py](../../external-research/linkding/bookmarks/api/serializers.py)
- Ручной CRUD и merge тегов: [bookmarks/views/tags.py](../../external-research/linkding/bookmarks/views/tags.py)
- Форма тегов и merge validation: [bookmarks/forms.py](../../external-research/linkding/bookmarks/forms.py)
- Настройки i18n middleware: [bookmarks/settings/base.py](../../external-research/linkding/bookmarks/settings/base.py)
- Профиль пользователя с `auto_tagging_rules`: [bookmarks/models.py](../../external-research/linkding/bookmarks/models.py)
- UI profile form, где редактируются auto-tagging rules: [bookmarks/forms.py](../../external-research/linkding/bookmarks/forms.py)
- Bundles как сохранённые фильтры: [bookmarks/models.py](../../external-research/linkding/bookmarks/models.py)
- Применение bundles в query layer: [bookmarks/queries.py](../../external-research/linkding/bookmarks/queries.py)

