import { startTransition, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { createJob, getJobResult, getJobStatus, isApiClientError, pingReadiness } from "../lib/api";
import { DEMO_PRESETS, type DemoPreset } from "../lib/demo-presets";
import {
  buildCreateJobPayload,
  createRequestCard,
  normalizeApiBaseUrl,
  prependRequestCard,
  updateRequestCard,
} from "../lib/job-state";
import type { RequestCard, RequestDraft } from "../types/tagging";

const DEFAULT_API_BASE_URL = "/api/v1/tagging";

function createInitialDraft(): RequestDraft {
  return {
    apiBaseUrl: DEFAULT_API_BASE_URL,
    text: "",
    source: "article",
    title: "",
    language: "",
    collection: "",
    keywords: "",
    author: "",
    maxTags: 5,
    useLlmPostprocess: false,
    taggingMode: "generate",
    outputLanguage: "auto",
    enableRules: true,
    llmStrategy: "disabled",
  };
}

function randomId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }

  return `job-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function useTaggingStream() {
  const [draft, setDraft] = useState<RequestDraft>(createInitialDraft);
  const [cards, setCards] = useState<RequestCard[]>([]);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [apiStatus, setApiStatus] = useState<"unknown" | "checking" | "online" | "offline">(
    "unknown",
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const pollTimeouts = useRef<Map<string, number>>(new Map());

  const clearPoll = useCallback((localId: string) => {
    const timeoutId = pollTimeouts.current.get(localId);
    if (timeoutId) {
      window.clearTimeout(timeoutId);
      pollTimeouts.current.delete(localId);
    }
  }, []);

  useEffect(() => {
    return () => {
      for (const timeoutId of pollTimeouts.current.values()) {
        window.clearTimeout(timeoutId);
      }
      pollTimeouts.current.clear();
    };
  }, []);

  const runReadinessCheck = useCallback(async (apiBaseUrl: string) => {
    if (!normalizeApiBaseUrl(apiBaseUrl)) {
      setApiStatus("unknown");
      return;
    }

    setApiStatus("checking");
    try {
      await pingReadiness(apiBaseUrl);
      setApiStatus("online");
    } catch {
      setApiStatus("offline");
    }
  }, []);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      void runReadinessCheck(draft.apiBaseUrl);
    }, 250);

    return () => window.clearTimeout(timeout);
  }, [draft.apiBaseUrl, runReadinessCheck]);

  const pollJob = useCallback(
    async (apiBaseUrl: string, localId: string, jobId: string) => {
      try {
        const status = await getJobStatus(apiBaseUrl, jobId);

        setCards((current) =>
          updateRequestCard(current, localId, {
            status,
            phase: status.status === "queued" ? "queued" : status.status === "processing" ? "processing" : status.status,
          }),
        );

        if (status.status === "completed" && status.result_available) {
          const result = await getJobResult(apiBaseUrl, jobId);
          clearPoll(localId);
          setCards((current) =>
            updateRequestCard(current, localId, {
              status,
              result,
              phase: "completed",
            }),
          );
          return;
        }

        if (status.status === "failed") {
          clearPoll(localId);
          setCards((current) =>
            updateRequestCard(current, localId, {
              status,
              phase: "failed",
              error: status.error ?? { code: "job_failed", message: "Processing failed." },
            }),
          );
          return;
        }

        const timeoutId = window.setTimeout(() => {
          void pollJob(apiBaseUrl, localId, jobId);
        }, 1200);
        pollTimeouts.current.set(localId, timeoutId);
      } catch (error) {
        clearPoll(localId);
        const fallback = isApiClientError(error)
          ? { code: error.code, message: error.message }
          : { code: "network_error", message: "Could not reach the API while polling this job." };

        setCards((current) =>
          updateRequestCard(current, localId, {
            phase: "failed",
            error: fallback,
          }),
        );
      }
    },
    [clearPoll],
  );

  const applyPreset = useCallback((preset: DemoPreset) => {
    const metadata = preset.metadata ?? {};
    startTransition(() => {
      setDraft((current) => ({
        ...current,
        source: preset.source,
        title: preset.title ?? "",
        text: preset.text,
        language: typeof metadata.language === "string" ? metadata.language : "",
        collection: typeof metadata.collection === "string" ? metadata.collection : "",
        keywords: Array.isArray(metadata.keywords)
          ? metadata.keywords.join(", ")
          : typeof metadata.keywords === "string"
            ? metadata.keywords
            : "",
        author: typeof metadata.author === "string" ? metadata.author : "",
      }));
    });
  }, []);

  const reuseCard = useCallback((card: RequestCard) => {
    startTransition(() => {
      setDraft((current) => ({
        ...current,
        source: card.payload.source,
        title:
          typeof card.payload.metadata.title === "string" ? (card.payload.metadata.title as string) : "",
        text: card.payload.text,
        language:
          typeof card.payload.metadata.language === "string"
            ? (card.payload.metadata.language as string)
            : "",
        collection:
          typeof card.payload.metadata.collection === "string"
            ? (card.payload.metadata.collection as string)
            : "",
        keywords: Array.isArray(card.payload.metadata.keywords)
          ? (card.payload.metadata.keywords as string[]).join(", ")
          : typeof card.payload.metadata.keywords === "string"
            ? (card.payload.metadata.keywords as string)
            : "",
        author:
          typeof card.payload.metadata.author === "string"
            ? (card.payload.metadata.author as string)
            : "",
        maxTags: card.payload.options.max_tags,
        useLlmPostprocess: card.payload.options.use_llm_postprocess,
        taggingMode: card.payload.options.tagging_mode,
        outputLanguage: card.payload.options.output_language,
        enableRules: card.payload.options.enable_rules,
        llmStrategy: card.payload.options.llm_strategy,
      }));
    });
  }, []);

  const loadFile = useCallback((file: File) => {
    void file.text().then((text) => {
      setDraft((current) => ({
        ...current,
        text,
        title: current.title || file.name.replace(/\.[^.]+$/, ""),
      }));
    });
  }, []);

  const submit = useCallback(async () => {
    setSubmitError(null);
    setIsSubmitting(true);

    const localId = randomId();

    try {
      const payload = buildCreateJobPayload(draft);
      if (!payload.text) {
        throw new Error("Text is required.");
      }

      const optimisticCard = createRequestCard(localId, payload);
      setCards((current) => prependRequestCard(current, optimisticCard));

      const response = await createJob(draft.apiBaseUrl, payload);

      setCards((current) =>
        updateRequestCard(current, localId, {
          phase: response.status === "queued" ? "queued" : "processing",
          jobId: response.job_id,
          documentId: response.document_id,
        }),
      );
      setApiStatus("online");
      await pollJob(draft.apiBaseUrl, localId, response.job_id);
    } catch (error) {
      const message = isApiClientError(error)
        ? error.message
        : error instanceof Error
          ? error.message
          : "Unknown error while sending the request.";

      setSubmitError(message);
      setCards((current) =>
        current.some((card) => card.localId === localId)
          ? updateRequestCard(current, localId, {
              phase: "failed",
              error: {
                code: isApiClientError(error) ? error.code : "submit_failed",
                message,
              },
            })
          : current,
      );
    } finally {
      setIsSubmitting(false);
    }
  }, [draft, pollJob]);

  const stats = useMemo(
    () => ({
      total: cards.length,
      active: cards.filter((card) => card.phase === "queued" || card.phase === "processing").length,
      completed: cards.filter((card) => card.phase === "completed").length,
      failed: cards.filter((card) => card.phase === "failed").length,
    }),
    [cards],
  );

  return {
    draft,
    cards,
    stats,
    presets: DEMO_PRESETS,
    apiStatus,
    isSubmitting,
    submitError,
    setDraft,
    applyPreset,
    submit,
    reuseCard,
    loadFile,
    pingApi: () => runReadinessCheck(draft.apiBaseUrl),
  };
}
