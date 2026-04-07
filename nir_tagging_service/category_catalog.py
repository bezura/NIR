from __future__ import annotations

"""Static multilingual category taxonomy used by the classifier."""

from dataclasses import dataclass
from typing import Iterable


DEFAULT_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DESCRIPTION_EMBEDDING_WEIGHT = 0.8
PROTOTYPE_EMBEDDING_WEIGHT = 1.6
KEYWORDS_EMBEDDING_WEIGHT = 0.55


@dataclass(frozen=True, slots=True)
class CategoryDefinition:
    """Single taxonomy node with prototypes and child categories."""

    code: str
    label: str
    description: str
    prototypes: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    children: tuple["CategoryDefinition", ...] = ()

    @property
    def is_leaf(self) -> bool:
        """Return True when the node has no children."""

        return not self.children

    def embedding_texts(self) -> tuple[str, ...]:
        """Return deduplicated texts used to embed this category."""

        texts: list[str] = []
        seen: set[str] = set()

        for candidate in (
            self.description,
            *self.prototypes,
            ", ".join(self.keywords) if self.keywords else "",
        ):
            normalized = candidate.strip()
            if not normalized:
                continue
            dedupe_key = normalized.casefold()
            if dedupe_key in seen:
                continue
            texts.append(normalized)
            seen.add(dedupe_key)

        return tuple(texts)

    def weighted_embedding_texts(self) -> tuple[tuple[str, float], ...]:
        """Return deduplicated embedding texts together with field-aware weights."""

        weighted_texts: dict[str, tuple[str, float]] = {}
        candidates = (
            (self.description, DESCRIPTION_EMBEDDING_WEIGHT),
            *((prototype, PROTOTYPE_EMBEDDING_WEIGHT) for prototype in self.prototypes),
            (", ".join(self.keywords) if self.keywords else "", KEYWORDS_EMBEDDING_WEIGHT),
        )

        for candidate, weight in candidates:
            normalized = candidate.strip()
            if not normalized:
                continue
            dedupe_key = normalized.casefold()
            current = weighted_texts.get(dedupe_key)
            if current is None:
                weighted_texts[dedupe_key] = (normalized, float(weight))
                continue
            weighted_texts[dedupe_key] = (current[0], current[1] + float(weight))

        return tuple(weighted_texts.values())

    def walk(self) -> Iterable["CategoryDefinition"]:
        """Yield the current node and all descendants depth-first."""

        yield self
        for child in self.children:
            yield from child.walk()

    def leaves(self) -> Iterable["CategoryDefinition"]:
        """Yield leaf descendants only."""

        if self.is_leaf:
            yield self
            return
        for child in self.children:
            yield from child.leaves()


def iter_categories(categories: Iterable[CategoryDefinition]) -> Iterable[CategoryDefinition]:
    """Iterate all categories depth-first across multiple roots."""

    for category in categories:
        yield from category.walk()


def iter_leaf_categories(categories: Iterable[CategoryDefinition]) -> Iterable[CategoryDefinition]:
    """Iterate leaf categories across multiple taxonomy roots."""

    for category in categories:
        yield from category.leaves()


DEFAULT_CATEGORIES = [
    CategoryDefinition(
        code="technology",
        label="Технологии",
        description="Technology, software systems, ML platforms, data infrastructure, retrieval systems, observability, deployment, engineering architecture, технологии, инженерия, программные системы, инфраструктура данных.",
        prototypes=(
            "Technical material about software systems, platform architecture, APIs, infrastructure, or deployment.",
            "Документ про архитектуру систем, инженерную платформу, инфраструктуру или эксплуатацию сервиса.",
        ),
        keywords=(
            "technology",
            "software",
            "engineering",
            "platform",
            "infrastructure",
            "технологии",
            "инженерия",
        ),
        children=(
            CategoryDefinition(
                code="technology_software",
                label="Технологии и разработка",
                description="Software architecture, backend services, API design, deployment, observability, retrieval systems, технологии, разработка, архитектура сервиса, backend-сервисы, проектирование API, эксплуатация сервиса.",
                prototypes=(
                    "Technical design document for a backend service, APIs, deployment, and observability.",
                    "System architecture note about vector search, indexing, reranking, and retrieval pipelines.",
                    "Документ по архитектуре сервиса, API, индексации, мониторингу и эксплуатации.",
                ),
                keywords=(
                    "software engineering",
                    "backend",
                    "api",
                    "service architecture",
                    "semantic search",
                    "retrieval pipeline",
                    "vector database",
                    "deployment",
                    "observability",
                    "разработка",
                    "архитектура сервиса",
                    "инфраструктура",
                    "мониторинг",
                ),
                children=(
                    CategoryDefinition(
                        code="technology_software_architecture",
                        label="Архитектура ПО и платформ",
                        description="System architecture, backend platform design, service boundaries, async pipelines, observability, deployment constraints, API contracts, микросервисная архитектура, backend платформа, архитектура сервиса, сервисные контракты.",
                        prototypes=(
                            "Architecture document for a backend platform, service boundaries, queues, APIs, deployment, and observability.",
                            "Engineering memo about ingestion pipelines, workers, API gateway, indexing, and platform lifecycle.",
                            "Документ по архитектуре платформы, пайплайнам обработки, очередям, API и эксплуатационным требованиям.",
                        ),
                        keywords=(
                            "system architecture",
                            "backend platform",
                            "microservice",
                            "api gateway",
                            "observability",
                            "deployment",
                            "architecture document",
                            "архитектура платформы",
                            "микросервис",
                            "очередь",
                            "контракты api",
                        ),
                    ),
                    CategoryDefinition(
                        code="technology_software_retrieval",
                        label="Поиск и retrieval-системы",
                        description="Retrieval systems, semantic search, lexical search, reranking, vector database, chunking, indexing, retrieval pipeline, информационный поиск, semantic search, retrieval pipeline, векторный поиск.",
                        prototypes=(
                            "Technical note about semantic search, retrieval pipelines, vector databases, reranking, and indexing.",
                            "Architecture description of a search platform with BM25, embeddings, chunk selection, and ranking.",
                            "Документ про retrieval pipeline, semantic search, векторную базу данных, chunking и reranking.",
                        ),
                        keywords=(
                            "semantic search",
                            "retrieval pipeline",
                            "vector database",
                            "reranking",
                            "bm25",
                            "indexing",
                            "retrieval platform",
                            "информационный поиск",
                            "векторный поиск",
                            "чанки",
                        ),
                    ),
                    CategoryDefinition(
                        code="technology_software_tooling",
                        label="Инструменты и developer tooling",
                        description="Developer tools, CLI tools, framework usage notes, installation guides, repository structure, build workflows, инженерные инструменты, cli, tooling, quickstart, developer workflow.",
                        prototypes=(
                            "README-style note describing a CLI tool, installation options, quickstart, and developer workflow.",
                            "Tooling summary covering repository structure, commands, test runs, and local setup.",
                            "Описание developer-инструмента с quickstart, установкой, командами и структурой репозитория.",
                        ),
                        keywords=(
                            "cli",
                            "quickstart",
                            "readme",
                            "developer tool",
                            "installation",
                            "workspace",
                            "tooling",
                            "cli tool",
                            "инструмент",
                            "быстрый старт",
                        ),
                    ),
                    CategoryDefinition(
                        code="technology_software_stack_selection",
                        label="Выбор стека и технические решения",
                        description="Technology selection, architecture trade-offs, library comparison, framework choice, implementation format, design decisions, выбор стека, сравнение библиотек, техническое решение, выбор framework.",
                        prototypes=(
                            "Technical decision memo comparing frameworks, libraries, and service formats for an implementation.",
                            "Architecture note explaining why a given stack or deployment approach was selected.",
                            "Документ с обоснованием выбора стека, библиотек, framework и формата сервиса.",
                        ),
                        keywords=(
                            "stack selection",
                            "framework choice",
                            "library comparison",
                            "architecture tradeoff",
                            "technology decision",
                            "выбор стека",
                            "выбор библиотек",
                            "обоснование",
                        ),
                    ),
                ),
            ),
            CategoryDefinition(
                code="technology_ai_ml",
                label="AI, ML и data systems",
                description="Machine learning systems, NLP pipelines, embeddings, model evaluation, RAG systems, feature pipelines, MLOps, машинное обучение, NLP, embeddings, модели, пайплайны данных.",
                prototypes=(
                    "ML platform note about embeddings, model serving, feature pipelines, and evaluation.",
                    "Материал про ML/NLP пайплайн, embeddings, модели и качество inference.",
                ),
                keywords=(
                    "machine learning",
                    "nlp",
                    "embeddings",
                    "rag",
                    "mlops",
                    "машинное обучение",
                    "обработка языка",
                    "модели",
                ),
                children=(
                    CategoryDefinition(
                        code="technology_ai_ml_nlp_rag",
                        label="NLP, embeddings и RAG",
                        description="NLP systems, embeddings, RAG, keyphrase extraction, tagging, model evaluation, sentence transformers, multilingual NLP, NLP пайплайны, embeddings, категоризация, тегирование.",
                        prototypes=(
                            "NLP system note about embeddings, tagging, categorization, multilingual processing, or RAG.",
                            "Document describing sentence embeddings, keyphrase extraction, tagging quality, and evaluation.",
                            "Материал про embeddings, NLP-пайплайн, категоризацию, тегирование и оценку качества.",
                        ),
                        keywords=(
                            "nlp",
                            "rag",
                            "embeddings",
                            "tagging",
                            "categorization",
                            "keyphrase extraction",
                            "sentence transformers",
                            "multilingual nlp",
                            "обработка языка",
                            "тегирование",
                            "категоризация",
                        ),
                    ),
                    CategoryDefinition(
                        code="technology_ai_ml_applied",
                        label="Прикладные AI-инструменты",
                        description="Applied AI products and tools, voice cloning, speech synthesis, image generation, 3D scene generation, local AI studio, прикладные AI-инструменты, voice cloning, image generation.",
                        prototypes=(
                            "Announcement or product note about an AI tool for voice, image, or generative media workflows.",
                            "Short description of a local AI studio, multimodal generation, or creative ML tool.",
                            "Короткое описание AI-инструмента для генерации изображений, речи, 3D-сцен или мультимодального контента.",
                        ),
                        keywords=(
                            "voice cloning",
                            "speech synthesis",
                            "image generation",
                            "3d scene",
                            "local models",
                            "ai studio",
                            "генерация изображений",
                            "синтез речи",
                            "клонирование голоса",
                        ),
                    ),
                ),
            ),
        ),
    ),
    CategoryDefinition(
        code="research",
        label="Исследования",
        description="Research documents, methodology, literature review, experiments, benchmarks, scientific analysis, исследования, научная методология, обзор литературы, эксперименты, бенчмарки.",
        prototypes=(
            "Research artifact describing methodology, experiments, hypotheses, or literature review.",
            "Научный или исследовательский документ с постановкой задачи, методами и анализом результатов.",
        ),
        keywords=(
            "research",
            "methodology",
            "literature review",
            "experiment",
            "benchmark",
            "исследование",
            "методология",
        ),
        children=(
            CategoryDefinition(
                code="science_research",
                label="Наука и исследования",
                description="Scientific research, literature reviews, research design, experiments, methodology, benchmarks, multilingual evaluation, topic modeling, keyphrase extraction studies, исследования, научные статьи, литературный обзор, методы, эксперименты, бенчмарки, НИР.",
                prototypes=(
                    "Research paper discussing methods, datasets, benchmarks, hypotheses, and experimental results.",
                    "Literature review comparing prior work on multilingual evaluation, tagging, and categorization.",
                    "Научная статья с постановкой задачи, обзором литературы, экспериментами и анализом результатов.",
                ),
                keywords=(
                    "research paper",
                    "literature review",
                    "methodology",
                    "experiment",
                    "benchmark",
                    "multilingual evaluation",
                    "error analysis",
                    "научная статья",
                    "литературный обзор",
                    "эксперимент",
                    "методология",
                    "НИР",
                ),
                children=(
                    CategoryDefinition(
                        code="research_literature_review",
                        label="Литературный обзор",
                        description="Literature review, scoping review, prior work analysis, survey of methods, обзор литературы, scoping review, анализ предыдущих работ.",
                        prototypes=(
                            "Literature review comparing prior work, methods, and limitations across a research area.",
                            "Scoping review draft with search strategy, inclusion criteria, and synthesis of prior studies.",
                            "Литературный обзор с анализом предыдущих работ, методов, ограничений и направлений исследований.",
                        ),
                        keywords=(
                            "literature review",
                            "scoping review",
                            "survey",
                            "prior work",
                            "обзор литературы",
                            "анализ работ",
                            "search strategy",
                        ),
                    ),
                    CategoryDefinition(
                        code="research_methodology",
                        label="Исследовательская методология",
                        description="Research design, methodology, inclusion criteria, annotation protocol, reproducibility, sampling strategy, исследовательская методология, дизайн исследования, воспроизводимость.",
                        prototypes=(
                            "Methodology note describing research questions, inclusion criteria, protocol, annotation, and reproducibility.",
                            "Research planning document focused on experimental setup and methodological choices.",
                            "Документ про методологию исследования, критерии отбора, протокол и воспроизводимость.",
                        ),
                        keywords=(
                            "methodology",
                            "research design",
                            "protocol",
                            "inclusion criteria",
                            "annotation",
                            "reproducibility",
                            "методология",
                            "дизайн исследования",
                        ),
                    ),
                    CategoryDefinition(
                        code="research_benchmark_evaluation",
                        label="Бенчмарки и оценка",
                        description="Benchmarking, metrics, evaluation protocols, error analysis, precision@k, pass@k, multilingual evaluation, benchmark design, бенчмарк, метрики, оценивание, анализ ошибок.",
                        prototypes=(
                            "Research note focused on benchmarks, evaluation metrics, protocols, and error analysis.",
                            "Experimental write-up centered on quality measurement, benchmark design, and result interpretation.",
                            "Исследовательский документ про бенчмарки, метрики, оценивание качества и анализ ошибок.",
                        ),
                        keywords=(
                            "benchmark",
                            "evaluation",
                            "metrics",
                            "error analysis",
                            "precision@k",
                            "pass@k",
                            "benchmark design",
                            "multilingual evaluation",
                            "бенчмарк",
                            "оценивание",
                            "метрики",
                        ),
                    ),
                ),
            ),
        ),
    ),
    CategoryDefinition(
        code="education",
        label="Образование",
        description="Education and training materials, syllabi, tutorials, assignments, learning plans, обучение, курсы, учебные материалы, практикумы.",
        children=(
            CategoryDefinition(
                code="education_learning",
                label="Образование и обучение",
                description="Learning materials, course plans, syllabi, tutorials, workshop notes, assignments, teaching guides, educational methodology, обучение, учебные материалы, программа курса, лабораторные задания, практикум, методические рекомендации.",
                prototypes=(
                    "Course syllabus with weekly topics, assignments, labs, and learning outcomes.",
                    "Tutorial explaining concepts step by step for students or trainees.",
                    "Учебно-методический документ с лекциями, практиками, заданиями и критериями оценки.",
                ),
                keywords=(
                    "course",
                    "syllabus",
                    "lecture",
                    "lab",
                    "assignment",
                    "tutorial",
                    "обучение",
                    "курс",
                    "практикум",
                    "методические рекомендации",
                ),
                children=(
                    CategoryDefinition(
                        code="education_course_material",
                        label="Курс и учебные материалы",
                        description="Course syllabi, tutorial notes, lecture plans, teaching guides, учебные материалы, syllabus, tutorial, лекции, программа курса.",
                        prototypes=(
                            "Course syllabus with weekly topics, reading list, lectures, and learning outcomes.",
                            "Tutorial-style educational material explaining a framework or concept step by step.",
                            "Учебный материал с программой курса, лекциями, литературой и ожидаемыми результатами.",
                        ),
                        keywords=(
                            "course",
                            "syllabus",
                            "tutorial",
                            "lecture",
                            "learning outcomes",
                            "курс",
                            "программа курса",
                            "лекция",
                            "учебный материал",
                        ),
                    ),
                    CategoryDefinition(
                        code="education_practicum_lab",
                        label="Практикум и лабораторные",
                        description="Practicum, lab assignments, project-based learning, hands-on educational tasks, лабораторные работы, практикум, задания, проектная работа.",
                        prototypes=(
                            "Practicum document with labs, assignments, project tasks, and grading criteria.",
                            "Hands-on course plan focused on laboratory work, reports, and project defense.",
                            "Документ по практикуму с лабораторными, заданиями, отчётами и проектной работой.",
                        ),
                        keywords=(
                            "practicum",
                            "lab",
                            "assignment",
                            "project work",
                            "лабораторная",
                            "практикум",
                            "задание",
                            "проект",
                        ),
                    ),
                    CategoryDefinition(
                        code="education_assessment_guidelines",
                        label="Оценивание и требования",
                        description="Assessment guidelines, rubrics, checkpoints, grading criteria, formal educational requirements, фонд оценочных средств, критерии оценивания, контрольные точки.",
                        prototypes=(
                            "Assessment document describing checkpoints, rubrics, deadlines, and formal grading criteria.",
                            "Educational regulation for student research with deliverables, milestones, and evaluation rules.",
                            "Документ с критериями оценивания, дедлайнами, чек-листами и требованиями к учебной работе.",
                        ),
                        keywords=(
                            "assessment",
                            "rubric",
                            "grading criteria",
                            "checkpoints",
                            "deliverables",
                            "фос",
                            "критерии оценивания",
                            "контрольные точки",
                            "дедлайн",
                        ),
                    ),
                ),
            ),
        ),
    ),
    CategoryDefinition(
        code="governance",
        label="Право и регулирование",
        description="Law, policy, regulation, compliance, governance, legal requirements, право, регулирование, внутренние регламенты, compliance.",
        children=(
            CategoryDefinition(
                code="law_policy",
                label="Право и регулирование",
                description="Laws, regulations, privacy requirements, compliance, governance, internal policy, правовые нормы, нормативные документы, согласие на обработку данных, регулирование, compliance, governance.",
                prototypes=(
                    "Policy document describing legal obligations, governance, compliance controls, and retention rules.",
                    "Регламент по обработке данных, правовым требованиям и внутреннему контролю.",
                ),
                keywords=(
                    "law",
                    "regulation",
                    "policy",
                    "compliance",
                    "privacy",
                    "право",
                    "регламент",
                    "нормативный документ",
                    "персональные данные",
                ),
                children=(
                    CategoryDefinition(
                        code="governance_compliance_policy",
                        label="Compliance и policy",
                        description="Compliance policy, privacy requirements, data handling rules, legal obligations, governance controls, policy documents, compliance policy, privacy policy, регламент по данным.",
                        prototypes=(
                            "Policy document covering privacy, data retention, consent, and internal compliance obligations.",
                            "Internal governance and compliance policy with responsibilities and mandatory controls.",
                            "Политика и регламент по персональным данным, срокам хранения и соблюдению compliance-требований.",
                        ),
                        keywords=(
                            "compliance policy",
                            "privacy policy",
                            "data retention",
                            "consent",
                            "governance",
                            "политика",
                            "персональные данные",
                            "срок хранения",
                        ),
                    ),
                ),
            ),
        ),
    ),
    CategoryDefinition(
        code="business",
        label="Бизнес и продукт",
        description="Business, product strategy, roadmaps, market analysis, customer research, management decisions, бизнес, продукт, стратегия, roadmap.",
        children=(
            CategoryDefinition(
                code="business_product",
                label="Бизнес и продукт",
                description="Product strategy, roadmap, market analysis, monetization, customer research, KPI review, management decisions, продукт, бизнес, рынок, стратегия, развитие продукта, roadmap, метрики продукта.",
                prototypes=(
                    "Product memo about roadmap, activation, retention, conversion, and monetization.",
                    "Market and business analysis discussing priorities, customer needs, and expected impact.",
                    "Продуктовая записка с roadmap, KPI, гипотезами роста и бизнес-приоритетами.",
                ),
                keywords=(
                    "product strategy",
                    "roadmap",
                    "market analysis",
                    "retention",
                    "conversion",
                    "monetization",
                    "продукт",
                    "бизнес",
                    "рынок",
                    "метрики",
                ),
                children=(
                    CategoryDefinition(
                        code="business_product_strategy",
                        label="Продуктовая стратегия",
                        description="Product strategy, monetization, customer research, KPI review, growth hypotheses, продуктовая стратегия, customer research, monetization.",
                        prototypes=(
                            "Product memo about KPIs, customer needs, monetization, and strategic priorities.",
                            "Business analysis connecting product hypotheses to impact, retention, or revenue outcomes.",
                            "Продуктовая записка с гипотезами роста, метриками, исследованием пользователей и стратегическими решениями.",
                        ),
                        keywords=(
                            "product strategy",
                            "customer research",
                            "monetization",
                            "kpi",
                            "growth hypothesis",
                            "продуктовая стратегия",
                            "монетизация",
                            "пользовательское исследование",
                        ),
                    ),
                    CategoryDefinition(
                        code="business_roadmap_review",
                        label="Roadmap и квартальные обзоры",
                        description="Roadmap review, quarterly planning, initiative prioritization, activation, retention, conversion trade-offs, roadmap review, quarterly priorities, квартальный обзор roadmap.",
                        prototypes=(
                            "Quarterly roadmap review discussing initiative priorities, conversion, activation, retention, and expected impact.",
                            "Planning memo comparing roadmap options and business trade-offs for the next quarter.",
                            "Обзор roadmap и приоритетов квартала с анализом метрик, инициатив и ожидаемого эффекта.",
                        ),
                        keywords=(
                            "roadmap review",
                            "quarterly plan",
                            "prioritization",
                            "activation",
                            "retention",
                            "conversion",
                            "roadmap",
                            "приоритеты квартала",
                            "обзор roadmap",
                        ),
                    ),
                ),
            ),
        ),
    ),
    CategoryDefinition(
        code="personal",
        label="Личные заметки",
        description="Personal notes, reminders, drafts, scratchpads, personal knowledge base, личные заметки, напоминания, черновики, конспекты.",
        children=(
            CategoryDefinition(
                code="personal_knowledge",
                label="Личные заметки и знания",
                description="Personal notes, reminders, idea backlog, scratchpad, private journal, todo notes, рабочие наброски, личные заметки, напоминания, идеи для себя, конспекты, черновики.",
                prototypes=(
                    "Personal working note with reminders, draft ideas, and a checklist for later.",
                    "Черновая заметка для себя с мыслями, вопросами и напоминаниями.",
                ),
                keywords=(
                    "personal note",
                    "reminder",
                    "brainstorm",
                    "scratchpad",
                    "todo",
                    "личная заметка",
                    "напоминание",
                    "черновик",
                    "идеи",
                ),
                children=(
                    CategoryDefinition(
                        code="personal_working_notes",
                        label="Рабочие заметки",
                        description="Working notes, reminders, scratchpads, meeting prep, ad hoc notes, рабочие заметки, напоминания, конспекты, черновые записи.",
                        prototypes=(
                            "Working note with reminders, follow-ups, and rough points for later discussion.",
                            "Personal scratchpad containing short operational notes and next actions.",
                            "Рабочая заметка с напоминаниями, вопросами и короткими записями для себя.",
                        ),
                        keywords=(
                            "working note",
                            "reminder",
                            "scratchpad",
                            "follow-up",
                            "рабочая заметка",
                            "напоминание",
                            "конспект",
                        ),
                    ),
                    CategoryDefinition(
                        code="personal_ideas_backlog",
                        label="Идеи и backlog",
                        description="Ideas backlog, brainstorm list, future improvements, todo ideas, список идей, backlog, наброски улучшений.",
                        prototypes=(
                            "Idea backlog listing future improvements, experiments, and items to revisit later.",
                            "Short note with backlog items, hypotheses, and thoughts for a future sprint.",
                            "Список идей и backlog с гипотезами, задачами и улучшениями на будущее.",
                        ),
                        keywords=(
                            "ideas backlog",
                            "brainstorm",
                            "todo ideas",
                            "future improvements",
                            "идеи",
                            "backlog",
                            "гипотезы",
                            "улучшения",
                        ),
                    ),
                ),
            ),
        ),
    ),
]
