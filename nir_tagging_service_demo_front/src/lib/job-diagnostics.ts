import type { RequestCard } from "../types/tagging";
import { clamp, safeRecord } from "./utils";

export interface ProgressSummary {
  label: string;
  percent: number;
  currentStage: string | null;
}

export function getSignals(card: RequestCard) {
  return safeRecord(card.result?.signals);
}

export function getClassificationSignals(card: RequestCard) {
  const signals = getSignals(card);
  return safeRecord(signals?.classification);
}

export function getTimingEntries(card: RequestCard) {
  const signals = getSignals(card);
  const timings = safeRecord(signals?.timings_ms);
  if (!timings) {
    return [];
  }

  return Object.entries(timings)
    .filter(([, value]) => typeof value === "number")
    .map(([key, value]) => ({
      key,
      value: `${Math.round(value as number)} ms`,
    }));
}

export function getLanguageSummary(card: RequestCard) {
  const signals = getSignals(card);
  const language = safeRecord(signals?.language);
  if (!language) {
    return null;
  }

  const distribution = safeRecord(language.distribution);
  const dominant = typeof language.dominant === "string" ? language.dominant : null;
  const secondary = typeof language.secondary === "string" ? language.secondary : null;
  const mixed = language.mixed === true ? "mixed" : null;

  const parts = [dominant, secondary, mixed].filter(Boolean) as string[];
  if (distribution) {
    const topShares = Object.entries(distribution)
      .filter(([, value]) => typeof value === "number" && (value as number) > 0)
      .sort((left, right) => Number(right[1]) - Number(left[1]))
      .slice(0, 2)
      .map(([key, value]) => `${key}:${Math.round(Number(value) * 100)}%`);
    parts.push(...topShares);
  }

  return parts.length > 0 ? parts.join(" · ") : null;
}

export function getResultFacts(card: RequestCard) {
  const signals = getSignals(card);
  const classification = getClassificationSignals(card);
  const pipeline = safeRecord(signals?.pipeline);

  const facts: Array<{ label: string; value: string }> = [];
  const chunked = signals?.chunked;
  const numChunks = signals?.num_chunks;

  if (typeof chunked === "boolean") {
    facts.push({ label: "chunked", value: chunked ? "yes" : "no" });
  }

  if (typeof numChunks === "number") {
    facts.push({ label: "chunks", value: String(numChunks) });
  }

  if (classification && typeof classification.confidence_gap === "number") {
    facts.push({ label: "gap", value: classification.confidence_gap.toFixed(3) });
  }

  if (classification && typeof classification.low_confidence === "boolean") {
    facts.push({ label: "confidence", value: classification.low_confidence ? "low" : "ok" });
  }

  if (typeof pipeline?.tagging_mode === "string") {
    facts.push({ label: "mode", value: pipeline.tagging_mode });
  }

  if (typeof pipeline?.output_language === "string") {
    facts.push({ label: "output", value: pipeline.output_language });
  }

  if (typeof pipeline?.enable_rules === "boolean") {
    facts.push({ label: "rules", value: pipeline.enable_rules ? "on" : "off" });
  }

  if (typeof pipeline?.llm_strategy === "string") {
    facts.push({ label: "llm", value: pipeline.llm_strategy });
  }

  return facts;
}

export function getProgressSummary(card: RequestCard): ProgressSummary {
  const status = card.status;
  const percentFromStatus = typeof status?.progress_percent === "number" ? status.progress_percent : null;
  const labelFromStatus = typeof status?.stage_label === "string" ? status.stage_label : null;
  const currentStage = typeof status?.current_stage === "string" ? status.current_stage : null;

  let fallbackPercent = 0;
  let fallbackLabel = "В очереди";
  if (card.phase === "processing") {
    fallbackPercent = 50;
    fallbackLabel = "Обработка";
  } else if (card.phase === "completed") {
    fallbackPercent = 100;
    fallbackLabel = "Готово";
  } else if (card.phase === "failed") {
    fallbackPercent = 100;
    fallbackLabel = "Ошибка";
  }

  return {
    label: labelFromStatus ?? fallbackLabel,
    percent: clamp(percentFromStatus ?? fallbackPercent, 0, 100),
    currentStage,
  };
}

export function getStageEntries(card: RequestCard) {
  const history = card.status?.stage_history ?? [];
  const pending = card.status?.pending_stages ?? [];
  return [...history, ...pending];
}
