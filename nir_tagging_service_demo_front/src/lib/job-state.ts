import type { CreateJobPayload, RequestCard, RequestDraft } from "../types/tagging";
import { shortenText } from "./utils";

export function normalizeApiBaseUrl(value: string) {
  return value.trim().replace(/\/+$/, "");
}

function splitKeywords(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function buildCreateJobPayload(draft: RequestDraft): CreateJobPayload {
  const metadata: Record<string, unknown> = {};
  const title = draft.title.trim();
  const language = draft.language.trim();
  const collection = draft.collection.trim();
  const keywords = splitKeywords(draft.keywords);
  const author = draft.author.trim();

  if (title) {
    metadata.title = title;
  }
  if (language) {
    metadata.language = language;
  }
  if (collection) {
    metadata.collection = collection;
  }
  if (keywords.length > 0) {
    metadata.keywords = keywords;
  }
  if (author) {
    metadata.author = author;
  }

  return {
    text: draft.text.trim(),
    source: draft.source,
    metadata,
    options: {
      max_tags: draft.maxTags,
      use_llm_postprocess: draft.useLlmPostprocess,
      tagging_mode: draft.taggingMode,
      output_language: draft.outputLanguage,
      enable_rules: draft.enableRules,
      llm_strategy: draft.llmStrategy,
    },
  };
}

export function createRequestCard(localId: string, payload: CreateJobPayload): RequestCard {
  const titleFromMetadata =
    typeof payload.metadata.title === "string" ? payload.metadata.title.trim() : "";

  return {
    localId,
    createdAt: Date.now(),
    phase: "queued",
    payload,
    title: titleFromMetadata || "Untitled request",
    preview: shortenText(payload.text),
  };
}

export function prependRequestCard(cards: RequestCard[], nextCard: RequestCard) {
  return [nextCard, ...cards];
}

export function updateRequestCard(
  cards: RequestCard[],
  localId: string,
  patch: Partial<RequestCard>,
) {
  return cards.map((card) => (card.localId === localId ? { ...card, ...patch } : card));
}
