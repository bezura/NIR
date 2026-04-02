# Рекомендации по развитию подсистемы тегирования и категоризации NIR

## 1. Основа для рекомендаций

- Этот документ собран по результатам анализа:
- [Karakeep](./karakeep.md)
- [Linkwarden](./linkwarden.md)
- [Linkding](./linkding.md)
- [Briefkasten](./briefkasten.md)
- Текущее состояние вашей подсистемы проверено по коду:
- [nir_tagging_service/pipeline.py](../../nir_tagging_service/pipeline.py)
- [nir_tagging_service/tag_extraction.py](../../nir_tagging_service/tag_extraction.py)
- [nir_tagging_service/categorization.py](../../nir_tagging_service/categorization.py)
- [nir_tagging_service/language.py](../../nir_tagging_service/language.py)
- [nir_tagging_service/llm_enhancement.py](../../nir_tagging_service/llm_enhancement.py)
- [nir_tagging_service/schemas.py](../../nir_tagging_service/schemas.py)
- [nir_tagging_service/db/models.py](../../nir_tagging_service/db/models.py)

## 2. Что уже хорошо сделано в NIR

- Уже есть сильная базовая схема `category -> tags -> optional llm`.
- Категоризация в [nir_tagging_service/categorization.py](../../nir_tagging_service/categorization.py) уже учитывает иерархию категорий и близость по embeddings.
- Извлечение тегов в [nir_tagging_service/tag_extraction.py](../../nir_tagging_service/tag_extraction.py) уже построено на нескольких стратегиях и умеет работать с RU/EN.
- В [nir_tagging_service/language.py](../../nir_tagging_service/language.py) уже есть полезное определение языкового профиля документа.
- В [nir_tagging_service/llm_enhancement.py](../../nir_tagging_service/llm_enhancement.py) уже есть точка расширения для дополнительной интеллектуальной обработки.

Проблема сейчас не в отсутствии пайплайна, а в том, что он пока недостаточно управляемый: нет явного происхождения тегов, нет словаря канонических тегов, нет rule-layer перед ML/LLM, и LLM пока больше "улучшает", чем работает в жёстких рамках.

## 3. Что улучшать в первую очередь

### 3.1. Добавить происхождение тега

Лучший референс: [Karakeep](./karakeep.md)

Сейчас в ответе и в сохранённых результатах у тега нет признака происхождения. Нужно добавить как минимум:

- `manual`
- `rule`
- `model`
- `llm`

Это позволит:

- не смешивать детерминированные и вероятностные теги;
- обновлять только автоматически созданный слой;
- считать качество по каждому типу происхождения отдельно;
- хранить доверие к тегу без потери прозрачности.

Что менять:

- [nir_tagging_service/schemas.py](../../nir_tagging_service/schemas.py): расширить `TagResponse`
- [nir_tagging_service/db/models.py](../../nir_tagging_service/db/models.py): расширить структуру `tags_json`
- [nir_tagging_service/pipeline.py](../../nir_tagging_service/pipeline.py): маркировать источник на каждом этапе

Рекомендуемые поля у тега:

- `source`
- `method`
- `confidence`
- `reason`
- `catalog_tag_id` или `canonical_name`

### 3.2. Добавить rule-based слой перед категоризацией и извлечением тегов

Лучший референс: [Linkding](./linkding.md), частично [Karakeep](./karakeep.md)

Сейчас основной интеллект идёт через embeddings, KeyBERT и optional LLM. Не хватает детерминированного слоя, который даёт быстрые и стабильные сигналы.

Что стоит добавить:

- правила по домену;
- правила по URL/path;
- правила по ключевым словам в `title`;
- правила по `source_type`, если он есть;
- правила по извлечённым метаданным;
- правила по языку документа.

Примеры:

- `arxiv.org` -> hint для категорий `research`, `paper`, `ml`
- `github.com` + `README` + `install` -> hint для `development`, `opensource`, `tooling`
- русскоязычный текст с терминами `закон`, `суд`, `статья` -> boost для юридического сегмента

Что менять:

- [nir_tagging_service/pipeline.py](../../nir_tagging_service/pipeline.py): добавить этап `apply_rules`
- [nir_tagging_service/schemas.py](../../nir_tagging_service/schemas.py): добавить `rule_profile` / `enable_rules`
- Новый модуль уровня `rules.py` или `rule_engine.py`

Рекомендуемая новая последовательность:

`language detection -> rule hints -> category scoring -> tag extraction -> tag reconciliation -> optional llm rerank`

### 3.3. Ввести канонический словарь тегов

Лучший референс: [Karakeep](./karakeep.md)

Сейчас тег живёт в основном как текстовая строка после нормализации. Для качественного авто-тегирования нужен канонический слой:

- каноническое имя;
- нормализованное имя;
- алиасы;
- язык отображения;
- допустимые синонимы;
- связь с категориями;
- признак `allowed/curated`.

Это даст:

- меньше дублей типа `AI`, `ai`, `artificial-intelligence`, `искусственный интеллект`;
- возможность режима `existing_only`;
- возможность режима `curated_only`;
- консистентные теги в ответе и в БД.

Что менять:

- [nir_tagging_service/tag_extraction.py](../../nir_tagging_service/tag_extraction.py): после извлечения делать match в каталог
- [nir_tagging_service/schemas.py](../../nir_tagging_service/schemas.py): добавить `tagging_mode`
- [nir_tagging_service/db/models.py](../../nir_tagging_service/db/models.py): предусмотреть хранение канонического идентификатора

Рекомендуемые режимы:

- `generate`: как сейчас, но с матчингом и нормализацией
- `existing_only`: разрешать только теги из словаря
- `curated_only`: разрешать только теги из выбранного набора
- `hybrid`: разрешать новые теги, но сначала пытаться матчить в словарь

### 3.4. Сделать теги зависимыми от категории

Лучший практический вывод из всех 4 проектов, особенно полезен для NIR

Сейчас категория и теги вычисляются последовательно, но почти независимо. Лучше сделать двухпроходную схему:

1. сначала получить топ категорий;
2. затем извлечь теги с учётом этих категорий;
3. затем перепроверить категорию с учётом уже подтверждённых тегов.

Это даст:

- меньше общих тегов;
- меньше нерелевантных тегов из соседних тем;
- более устойчивую финальную категорию.

Что менять:

- [nir_tagging_service/categorization.py](../../nir_tagging_service/categorization.py): добавить boosts от тегов
- [nir_tagging_service/tag_extraction.py](../../nir_tagging_service/tag_extraction.py): добавить category-conditioned rerank
- [nir_tagging_service/pipeline.py](../../nir_tagging_service/pipeline.py): добавить второй проход category reconciliation

## 4. Что улучшать вторым этапом

### 4.1. Разделить язык документа и язык выходных тегов

Лучший референс: [Karakeep](./karakeep.md)

Сейчас язык документа определяется хорошо, но полезно отдельно зафиксировать язык результата:

- документ может быть `mixed`;
- пользователь может хотеть теги только на русском;
- или наоборот, внутренний каталог тегов может быть англоязычным.

Что добавить:

- `output_language` в [nir_tagging_service/schemas.py](../../nir_tagging_service/schemas.py)
- приведение тегов к целевому языку на этапе reconciliation
- алиасы RU/EN в каноническом каталоге

Практический эффект:

- теги перестанут "скакать" между русским и английским;
- станет проще делать поиск и фильтрацию;
- будет проще объединять данные из mixed-language источников.

### 4.2. Ограничить LLM и превратить его в контролируемый этап

Лучшие референсы: [Karakeep](./karakeep.md), [Linkwarden](./linkwarden.md)

LLM лучше использовать не как свободный генератор тегов, а как узкий этап согласования в low-confidence случаях.

Правильные режимы:

- выбрать теги из предложенного списка;
- отранжировать уже найденные теги;
- предложить 1-2 дополнительных тега только из curated-словаря;
- подтвердить или оспорить категорию при низкой уверенности.

Что менять:

- [nir_tagging_service/llm_enhancement.py](../../nir_tagging_service/llm_enhancement.py): перейти от "freeform enhancement" к constrained output
- [nir_tagging_service/pipeline.py](../../nir_tagging_service/pipeline.py): вызывать LLM только при низкой уверенности или конфликте сигналов

Не рекомендуется:

- разрешать LLM без ограничений генерировать новые теги на каждом документе;
- использовать LLM как первый этап категоризации для всего потока.

### 4.3. Ввести единый стиль тегов

Лучший референс: [Karakeep](./karakeep.md)

Нужен единый tag style:

- `machine-learning`
- `machine_learning`
- `Machine Learning`

Нужно выбрать один формат как canonical, а пользовательский вид выводить отдельно при необходимости.

Что менять:

- [nir_tagging_service/tag_extraction.py](../../nir_tagging_service/tag_extraction.py): единый renderer финального тега
- каталог тегов: хранить `canonical_name` и `display_name`

## 5. Новые методы тегирования, которые стоит добавить

### 5.1. Rule-based auto-tagging

Источник идеи: [Linkding](./linkding.md)

Детерминированное назначение тегов по:

- домену;
- пути URL;
- title patterns;
- source-specific признакам;
- mime/content type;
- языку.

Это самый дешёвый и предсказуемый способ поднять precision.

### 5.2. Catalog-constrained tagging

Источник идеи: [Karakeep](./karakeep.md)

Извлечение идёт как сейчас, но финальные теги проходят через:

- словарь допустимых тегов;
- матчинг по алиасам;
- фильтр по категории;
- фильтр по языку.

Этот режим особенно полезен для production.

### 5.3. Category-conditioned tagging

Новый метод, хорошо ложится на ваш текущий pipeline

Сначала определяется топ-3 категории, потом один и тот же candidate tag получает разные веса в зависимости от их совместимости с категорией.

Пример:

- `transformer` в категории `nlp` получает boost;
- `transformer` в категории `power-engineering` не получает boost или получает penalty.

### 5.4. Hybrid score fusion

Новый метод для NIR

Финальный score тега можно считать как комбинацию:

- score из KeyBERT;
- score из embedding similarity к категории;
- rule boost;
- LLM confidence;
- наличие в curated catalog;
- частота использования тега в похожих документах.

Это даст более устойчивое ранжирование, чем один источник сигнала.

### 5.5. Alias and multilingual reconciliation

Новый метод для RU/EN mixed контента

Перед возвратом результата объединять:

- `ml`
- `machine learning`
- `машинное обучение`

в один канонический тег.

### 5.6. Incremental retagging

Источник идеи: [Karakeep](./karakeep.md)

При повторной обработке документа:

- не пересоздавать всё полностью;
- обновлять только автоматический слой;
- ручные теги не трогать;
- пересчитывать только теги с `source != manual`.

Это важно, если у вас позже появится ручная правка результатов.

## 6. Новые методы категоризации, которые стоит добавить

### 6.1. Rule-assisted categorization

Источник идеи: [Linkding](./linkding.md), [Karakeep](./karakeep.md)

Правила не должны заменять модель, но должны давать boosts/penalties для категории.

Это особенно полезно для:

- доменно-специфичных сайтов;
- корпоративных внутренних источников;
- повторяющихся структур контента.

### 6.2. Multi-candidate categorization с финальным выбором

Новый метод для NIR

Вместо немедленного выбора одной категории:

1. получить top-N кандидатов;
2. извлечь теги;
3. пересчитать category score на основе тегов и правил;
4. вернуть top-1 как primary, top-2/top-3 как alternatives.

Это уменьшит ошибки в пограничных случаях.

### 6.3. Low-confidence LLM adjudication

Источник идеи: [Linkwarden](./linkwarden.md), [Karakeep](./karakeep.md)

Если разница между top-1 и top-2 маленькая, можно:

- отправить только shortlist категорий;
- отправить ключевые фрагменты текста;
- попросить выбрать лучшую категорию из списка.

Это безопаснее, чем просить LLM придумать категорию с нуля.

### 6.4. Tag-to-category feedback

Новый метод для NIR

Некоторые теги должны явно усиливать или ослаблять конкретные категории.

Пример:

- `postgresql`, `sqlalchemy`, `orm` -> boost для backend/data
- `bert`, `tokenization`, `embedding` -> boost для nlp/ml

Это особенно хорошо дополняет вашу иерархическую категоризацию.

## 7. Конкретные изменения по текущему коду

### 7.1. [nir_tagging_service/pipeline.py](../../nir_tagging_service/pipeline.py)

Что изменить:

- добавить этап `rule_hints`;
- добавить этап `tag_reconciliation`;
- добавить второй проход category scoring после тегов;
- вызывать LLM только по условиям;
- логировать вклад каждого этапа.

Рекомендуемый pipeline:

`preprocess -> detect_language -> apply_rules -> initial_categorize -> extract_tag_candidates -> reconcile_with_catalog -> rerank_by_category -> low_confidence_llm -> finalize`

### 7.2. [nir_tagging_service/tag_extraction.py](../../nir_tagging_service/tag_extraction.py)

Что изменить:

- возвращать не только текст тега, но и происхождение/метод;
- добавить матчинг в catalog;
- добавить alias resolution;
- добавить category-conditioned rerank;
- добавить режимы `generate`, `existing_only`, `curated_only`, `hybrid`.

### 7.3. [nir_tagging_service/categorization.py](../../nir_tagging_service/categorization.py)

Что изменить:

- принимать rule hints;
- принимать boosts от тегов;
- уметь возвращать shortlist кандидатов;
- уметь объяснять, почему категория победила.

### 7.4. [nir_tagging_service/language.py](../../nir_tagging_service/language.py)

Что изменить:

- оставить текущий detection;
- добавить `output_language`;
- отдавать рекомендации для reconciliation слоя, а не только профиль текста.

### 7.5. [nir_tagging_service/llm_enhancement.py](../../nir_tagging_service/llm_enhancement.py)

Что изменить:

- перевести в constrained mode;
- запретить свободное создание тегов в strict-режимах;
- использовать только при low-confidence или конфликте источников;
- возвращать structured output с `selected_tags`, `rejected_tags`, `category_decision`, `reason`.

### 7.6. [nir_tagging_service/schemas.py](../../nir_tagging_service/schemas.py)

Что добавить:

- `tagging_mode`
- `output_language`
- `enable_rules`
- `rule_profile`
- `llm_strategy`
- поля происхождения и confidence в теге

### 7.7. [nir_tagging_service/db/models.py](../../nir_tagging_service/db/models.py)

Что добавить в сохраняемый результат:

- canonical tag id / canonical name;
- source;
- method;
- confidence;
- original raw label;
- reconciliation notes.

## 8. Что реально брать из каждого проекта

### 8.1. Из Karakeep

Брать обязательно:

- controlled AI tagging;
- curated tags;
- origin/provenance тега;
- разделение языка UI и языка inference;
- обновление только AI-слоя;
- tag style.

### 8.2. Из Linkding

Брать обязательно:

- rule-based auto-tagging;
- простые и прозрачные фильтры;
- предсказуемость без участия LLM.

### 8.3. Из Linkwarden

Брать выборочно:

- идею фоновой AI-обработки;
- встраивание AI в общий processing pipeline;
- условный запуск автоматизации после классификации.

### 8.4. Из Briefkasten

Брать минимально:

- только как пример простого разделения `tags` и `categories`.

Автоматизацию оттуда забирать почти нечего.

## 9. Что не стоит внедрять прямо сейчас

- свободную генерацию тегов LLM без словаря;
- сложный rule engine с десятками действий, если цель пока только классификация;
- archive/download workflows из [Linkwarden](./linkwarden.md);
- ручные-only подходы из [Briefkasten](./briefkasten.md);
- второстепенные UI-фичи раньше, чем появится качественный catalog и provenance.

## 10. Приоритетный план внедрения

### Этап 1. Быстрый рост качества

- provenance тегов;
- rule-based hints;
- constrained tagging modes;
- catalog matching;
- output language.

Это даст самый быстрый прирост точности и управляемости.

### Этап 2. Улучшение интеллектуального ранжирования

- category-conditioned tagging;
- tag-to-category feedback;
- multi-candidate categorization;
- alias reconciliation.

Это даст лучший баланс precision/recall.

### Этап 3. Точечный LLM

- low-confidence adjudication;
- curated-only LLM rerank;
- пояснения причин выбора категории и тегов.

Это даст точечное усиление без лишней стоимости и шума.

## 11. Итоговая рекомендация

Если выбирать только несколько изменений с максимальной пользой, то внедрять стоит в таком порядке:

1. provenance тегов;
2. rule-based слой до ML/LLM;
3. канонический каталог тегов с alias matching;
4. режимы `existing_only` и `curated_only`;
5. category-conditioned rerank;
6. LLM только как constrained fallback.

Если смотреть на доноров по ценности для NIR, то порядок такой:

1. [Karakeep](./karakeep.md)
2. [Linkding](./linkding.md)
3. [Linkwarden](./linkwarden.md)
4. [Briefkasten](./briefkasten.md)
