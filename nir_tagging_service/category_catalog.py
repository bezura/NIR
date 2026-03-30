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
        description="software engineering, programming, AI tools, semantic search, embeddings, retrieval systems, data infrastructure, технологии, разработка, программирование, семантический поиск, векторный поиск, архитектура сервиса",
    ),
    CategoryDefinition(
        code="science_research",
        label="Наука и исследования",
        description="scientific papers, literature review, research problem, experiments, methods, surveys, analytics, topic modeling, keyphrase extraction research, automatic tagging and categorization research, исследования, научные статьи, литературный обзор, научная проблема, методы, эксперименты, исследовательские заметки, НИР, исследовательское обоснование",
    ),
    CategoryDefinition(
        code="education_learning",
        label="Образование и обучение",
        description="learning materials, tutorials, courses, explainers, обучение, учебные материалы, курсы, методика",
    ),
    CategoryDefinition(
        code="law_policy",
        label="Право и регулирование",
        description="laws, regulations, compliance, policy, право, нормативные документы, регулирование, compliance",
    ),
    CategoryDefinition(
        code="business_product",
        label="Бизнес и продукт",
        description="product strategy, market analysis, management, monetization, продукт, бизнес, рынок, стратегия",
    ),
    CategoryDefinition(
        code="personal_knowledge",
        label="Личные заметки и знания",
        description="personal notes, journal, reminders, brainstorms, todo notes, personal reflections, личные заметки, напоминания, личные идеи, конспекты для себя",
    ),
]
