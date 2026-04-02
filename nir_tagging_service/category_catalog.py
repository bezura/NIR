from dataclasses import dataclass


DEFAULT_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


@dataclass(frozen=True, slots=True)
class CategoryDefinition:
    code: str
    label: str
    description: str


DEFAULT_CATEGORIES = [
    CategoryDefinition(
        code="technology_software",
        label="Технологии и разработка",
        description="software engineering, backend services, api design, programming, AI tools, semantic search, embeddings, vector databases, retrieval pipelines, data infrastructure, технологии, разработка, backend-сервисы, проектирование api, программирование, семантический поиск, векторные базы данных, retrieval pipeline, архитектура сервиса",
    ),
    CategoryDefinition(
        code="science_research",
        label="Наука и исследования",
        description="scientific papers, literature review, research problem, experiments, methods, surveys, analytics, benchmarks, multilingual evaluation, topic modeling, keyphrase extraction research, automatic tagging and categorization research, исследования, научные статьи, литературный обзор, научная проблема, методы, эксперименты, бенчмарки, multilingual evaluation, исследовательские заметки, НИР, исследовательское обоснование",
    ),
    CategoryDefinition(
        code="education_learning",
        label="Образование и обучение",
        description="learning materials, tutorials, courses, explainers, workshop notes, syllabus, assignments, обучение, учебные материалы, курсы, методика, программа курса, лабораторные задания, методические рекомендации",
    ),
    CategoryDefinition(
        code="law_policy",
        label="Право и регулирование",
        description="laws, regulations, compliance, policy, governance, правовые нормы, право, нормативные документы, регулирование, governance, compliance",
    ),
    CategoryDefinition(
        code="business_product",
        label="Бизнес и продукт",
        description="product strategy, market analysis, management, monetization, product discovery, roadmap, продукт, бизнес, рынок, стратегия, развитие продукта, roadmap",
    ),
    CategoryDefinition(
        code="personal_knowledge",
        label="Личные заметки и знания",
        description="personal notes, journal, reminders, brainstorms, todo notes, personal reflections, scratchpad, личные заметки, напоминания, личные идеи, конспекты для себя, рабочие наброски",
    ),
]
