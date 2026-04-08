import { describe, expect, it } from "vitest";

import { buildCreateJobPayload, prependRequestCard, updateRequestCard } from "./job-state";
import type { RequestCard, RequestDraft } from "../types/tagging";

describe("job-state helpers", () => {
  it("does not include title in metadata when it is blank", () => {
    const draft: RequestDraft = {
      apiBaseUrl: "http://127.0.0.1:8000/api/v1/tagging",
      text: "Test content",
      source: "article",
      title: "   ",
      language: "ru",
      collection: "",
      keywords: "search, embeddings",
      author: "",
      maxTags: 6,
      useLlmPostprocess: true,
      taggingMode: "generate",
      outputLanguage: "auto",
      enableRules: true,
      llmStrategy: "disabled",
    };

    expect(buildCreateJobPayload(draft)).toEqual({
      text: "Test content",
      source: "article",
      metadata: {
        language: "ru",
        keywords: ["search", "embeddings"],
      },
      options: {
        max_tags: 6,
        use_llm_postprocess: true,
        tagging_mode: "generate",
        output_language: "auto",
        enable_rules: true,
        llm_strategy: "disabled",
      },
    });
  });

  it("builds metadata from structured fields without any JSON editor", () => {
    const draft: RequestDraft = {
      apiBaseUrl: "http://127.0.0.1:8000/api/v1/tagging",
      text: "Test content",
      source: "document",
      title: "RAG Notes",
      language: "mixed",
      collection: "internal-lab",
      keywords: "rag, vector search, reranking",
      author: "NLP Team",
      maxTags: 5,
      useLlmPostprocess: false,
      taggingMode: "hybrid",
      outputLanguage: "auto",
      enableRules: true,
      llmStrategy: "disabled",
    };

    expect(buildCreateJobPayload(draft)).toEqual({
      text: "Test content",
      source: "document",
      metadata: {
        title: "RAG Notes",
        language: "mixed",
        collection: "internal-lab",
        keywords: ["rag", "vector search", "reranking"],
        author: "NLP Team",
      },
      options: {
        max_tags: 5,
        use_llm_postprocess: false,
        tagging_mode: "hybrid",
        output_language: "auto",
        enable_rules: true,
        llm_strategy: "disabled",
      },
    });
  });

  it("builds current api options for rules, language and llm strategy", () => {
    const draft: RequestDraft = {
      apiBaseUrl: "http://127.0.0.1:8000/api/v1/tagging",
      text: "Test content",
      source: "article",
      title: "Rules-aware payload",
      language: "",
      collection: "",
      keywords: "",
      author: "",
      maxTags: 4,
      useLlmPostprocess: false,
      taggingMode: "existing_only",
      outputLanguage: "ru",
      enableRules: false,
      llmStrategy: "low_confidence_only",
    };

    expect(buildCreateJobPayload(draft)).toEqual({
      text: "Test content",
      source: "article",
      metadata: {
        title: "Rules-aware payload",
      },
      options: {
        max_tags: 4,
        use_llm_postprocess: false,
        tagging_mode: "existing_only",
        output_language: "ru",
        enable_rules: false,
        llm_strategy: "low_confidence_only",
      },
    });
  });

  it("prepends a newer request card to the stream", () => {
    const older: RequestCard = {
      localId: "old",
      createdAt: 1,
      phase: "completed",
      payload: {
        text: "older",
        source: "note",
        metadata: {},
        options: {
          max_tags: 5,
          use_llm_postprocess: false,
          tagging_mode: "generate",
          output_language: "auto",
          enable_rules: true,
          llm_strategy: "disabled",
        },
      },
      title: "Older",
      preview: "older",
    };
    const newer: RequestCard = {
      localId: "new",
      createdAt: 2,
      phase: "queued",
      payload: {
        text: "newer",
        source: "article",
        metadata: {},
        options: {
          max_tags: 5,
          use_llm_postprocess: false,
          tagging_mode: "generate",
          output_language: "auto",
          enable_rules: true,
          llm_strategy: "disabled",
        },
      },
      title: "Newer",
      preview: "newer",
    };

    expect(prependRequestCard([older], newer).map((card) => card.localId)).toEqual(["new", "old"]);
  });

  it("updates only the targeted request card", () => {
    const cards: RequestCard[] = [
      {
        localId: "first",
        createdAt: 1,
        phase: "queued",
        payload: {
          text: "one",
          source: "note",
          metadata: {},
          options: {
            max_tags: 5,
            use_llm_postprocess: false,
            tagging_mode: "generate",
            output_language: "auto",
            enable_rules: true,
            llm_strategy: "disabled",
          },
        },
        title: "One",
        preview: "one",
      },
      {
        localId: "second",
        createdAt: 2,
        phase: "queued",
        payload: {
          text: "two",
          source: "note",
          metadata: {},
          options: {
            max_tags: 5,
            use_llm_postprocess: false,
            tagging_mode: "generate",
            output_language: "auto",
            enable_rules: true,
            llm_strategy: "disabled",
          },
        },
        title: "Two",
        preview: "two",
      },
    ];

    expect(
      updateRequestCard(cards, "second", {
        phase: "failed",
        error: { code: "boom", message: "Something broke" },
      }),
    ).toEqual([
      cards[0],
      {
        ...cards[1],
        phase: "failed",
        error: { code: "boom", message: "Something broke" },
      },
    ]);
  });
});
