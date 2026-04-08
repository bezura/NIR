import { describe, expect, it } from "vitest";

import { getLanguageSummary, getProgressSummary } from "./job-diagnostics";
import type { RequestCard } from "../types/tagging";

describe("job diagnostics helpers", () => {
  it("reads nested language signals from the current api contract", () => {
    const card: RequestCard = {
      localId: "job-1",
      createdAt: 1,
      phase: "completed",
      payload: {
        text: "hybrid retrieval",
        source: "document",
        metadata: {},
        options: {
          max_tags: 5,
          use_llm_postprocess: false,
          tagging_mode: "hybrid",
          output_language: "auto",
          enable_rules: true,
          llm_strategy: "disabled",
        },
      },
      title: "Hybrid retrieval",
      preview: "hybrid retrieval",
      result: {
        job_id: "job-1",
        document_id: "doc-1",
        category: {
          code: "technology_software",
          label: "Технологии и разработка",
          score: 0.84,
        },
        tags: [],
        score: 0.84,
        signals: {
          language: {
            dominant: "ru",
            secondary: "en",
            mixed: true,
            distribution: {
              ru: 0.61,
              en: 0.39,
            },
          },
        },
      },
    };

    expect(getLanguageSummary(card)).toBe("ru · en · mixed · ru:61% · en:39%");
  });

  it("prefers explicit stage labels and progress percent from job status", () => {
    const card: RequestCard = {
      localId: "job-2",
      createdAt: 1,
      phase: "processing",
      payload: {
        text: "semantic search",
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
      title: "Semantic search",
      preview: "semantic search",
      status: {
        job_id: "job-2",
        document_id: "doc-2",
        status: "processing",
        created_at: "2026-04-02T10:00:00Z",
        started_at: "2026-04-02T10:00:01Z",
        finished_at: null,
        result_available: false,
        current_stage: "tagging",
        stage_label: "Тегирование",
        progress_percent: 63,
        stage_history: [
          {
            name: "queued",
            label: "В очереди",
            status: "completed",
            started_at: "2026-04-02T10:00:00Z",
            finished_at: "2026-04-02T10:00:00Z",
          },
        ],
        pending_stages: [],
        error: null,
      },
    };

    expect(getProgressSummary(card)).toEqual({
      label: "Тегирование",
      percent: 63,
      currentStage: "tagging",
    });
  });
});
