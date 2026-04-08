import type { RequestDraft } from "../types/tagging";

export interface DemoPreset {
  id: string;
  label: string;
  eyebrow: string;
  source: RequestDraft["source"];
  title?: string;
  text: string;
  metadata?: Record<string, unknown>;
}

export const DEMO_PRESETS: DemoPreset[] = [
  {
    id: "semantic-search",
    label: "Semantic Search",
    eyebrow: "EN article",
    source: "article",
    title: "Embeddings for semantic search",
    text:
      "Transformer embeddings improve semantic search quality across support documents, while keyphrase extraction highlights the terms that explain why a document matched the query.",
    metadata: { language: "en", collection: "search-notes" },
  },
  {
    id: "mixed-rag",
    label: "Mixed RU/EN RAG",
    eyebrow: "RU/EN document",
    source: "document",
    title: "Гибридный retrieval pipeline для RAG",
    text:
      "Команда внедрила retrieval pipeline для внутренней базы знаний. В документе сравниваются hybrid search, reranking, chunk-level scoring и разные prompt templates. Авторы отдельно отмечают, что embeddings для русского корпуса работают заметно лучше, если в title и metadata сохраняются английские technical terms.",
    metadata: { language: "mixed", department: "nlp-lab" },
  },
  {
    id: "fastapi-recap",
    label: "FastAPI Recap",
    eyebrow: "Web page",
    source: "web_page",
    title: "FastAPI recap",
    text:
      "FastAPI gives automatic docs, data validation with type hints, async request handling and strong editor support. The main idea is to write regular Python functions, describe your input and output models, and let the framework generate a predictable API surface.",
    metadata: { language: "en", topic: "backend" },
  },
  {
    id: "vision-3d",
    label: "3D Scene Note",
    eyebrow: "RU note",
    source: "note",
    text:
      "Появилась нейросеть, которая превращает обычное фото в 3D-сцену: загружаете изображение, модель достраивает глубину и пространство, а потом можно двигать виртуальную камеру и смотреть на сцену под разными углами.",
    metadata: { language: "ru", channel: "social" },
  },
  {
    id: "voice-studio",
    label: "Voice Studio",
    eyebrow: "RU note",
    source: "note",
    text:
      "Вышла бесплатная ИИ-студия для работы с голосом: можно клонировать голос по нескольким секундам, генерировать речь, создавать озвучку, а локальные модели работают даже на обычном ноутбуке с 8 Гб ОЗУ.",
    metadata: { language: "ru", channel: "social" },
  },
];
