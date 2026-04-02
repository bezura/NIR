from dataclasses import dataclass


DEFAULT_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


@dataclass(frozen=True, slots=True)
class CategoryDefinition:
    code: str
    label: str
    description: str
    prototypes: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()

    def embedding_texts(self) -> tuple[str, ...]:
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


DEFAULT_CATEGORIES = [
    CategoryDefinition(
        code="technology_software",
        label="Технологии и разработка",
        description="Software architecture, engineering, backend services, API design, data and ML infrastructure, semantic search, retrieval systems, embeddings, vector databases, observability, deployment, технологии, разработка, архитектура сервиса, backend-сервисы, проектирование API, программирование, семантический поиск, retrieval pipeline, векторные базы данных, эксплуатация сервиса.",
        prototypes=(
            "Technical design document for a backend service, APIs, deployment, and observability.",
            "System architecture note about embeddings, vector search, indexing, reranking, and retrieval pipelines.",
            "Engineering implementation plan for semantic search, chunking, caching, and service lifecycle.",
            "Документ по архитектуре сервиса, API, индексации, мониторингу и эксплуатации.",
            "Техническое описание платформы с embeddings, vector database, retrieval pipeline и latency metrics.",
            "Материал о разработке, деплое, логировании, readiness, очередях задач и инфраструктуре сервиса.",
        ),
        keywords=(
            "software engineering",
            "backend",
            "api",
            "service architecture",
            "semantic search",
            "retrieval pipeline",
            "embeddings",
            "vector database",
            "deployment",
            "observability",
            "разработка",
            "архитектура сервиса",
            "инфраструктура",
            "мониторинг",
            "векторные базы данных",
        ),
    ),
    CategoryDefinition(
        code="science_research",
        label="Наука и исследования",
        description="Scientific research, literature reviews, research design, experiments, methodology, benchmarks, multilingual evaluation, topic modeling, keyphrase extraction, automatic tagging studies, исследования, научные статьи, литературный обзор, постановка научной проблемы, методы, эксперименты, бенчмарки, исследовательская методология, НИР.",
        prototypes=(
            "Research paper discussing methods, datasets, benchmarks, hypotheses, and experimental results.",
            "Literature review comparing prior work on multilingual evaluation, tagging, and categorization.",
            "Methodology note describing research questions, metrics, error analysis, and reproducible experiments.",
            "Научная статья с постановкой задачи, обзором литературы, экспериментами и анализом результатов.",
            "Литературный обзор по multilingual evaluation, keyphrase extraction и automatic categorization.",
            "Исследовательское обоснование с гипотезой, метриками, benchmark и обсуждением ограничений.",
        ),
        keywords=(
            "research paper",
            "literature review",
            "methodology",
            "experiment",
            "benchmark",
            "multilingual evaluation",
            "precision@k",
            "error analysis",
            "научная статья",
            "литературный обзор",
            "эксперимент",
            "методология",
            "исследование",
            "НИР",
        ),
    ),
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
    ),
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
    ),
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
    ),
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
    ),
]
