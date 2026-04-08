import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  ArrowUpRight,
  BrainCircuit,
  ChevronDown,
  ChevronUp,
  Clock3,
  CopyPlus,
  FileText,
  LoaderCircle,
  Tags,
} from "lucide-react";

import {
  getClassificationSignals,
  getLanguageSummary,
  getProgressSummary,
  getResultFacts,
  getStageEntries,
  getTimingEntries,
} from "../lib/job-diagnostics";
import { cn, formatClockTime, formatCompactDateTime } from "../lib/utils";
import type { RequestCard } from "../types/tagging";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";

interface JobCardProps {
  card: RequestCard;
  index: number;
  onReuse(card: RequestCard): void;
}

function phaseMeta(phase: RequestCard["phase"]) {
  switch (phase) {
    case "queued":
      return {
        label: "queued",
        variant: "active" as const,
        icon: <Clock3 className="h-3.5 w-3.5" />,
      };
    case "processing":
      return {
        label: "processing",
        variant: "active" as const,
        icon: <LoaderCircle className="h-3.5 w-3.5 animate-spin" />,
      };
    case "completed":
      return {
        label: "completed",
        variant: "success" as const,
        icon: <BrainCircuit className="h-3.5 w-3.5" />,
      };
    case "failed":
      return {
        label: "failed",
        variant: "danger" as const,
        icon: <AlertTriangle className="h-3.5 w-3.5" />,
      };
  }
}

function formatScore(value?: number) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return null;
  }

  return value.toFixed(3);
}

function ProgressRail({ percent }: { percent: number }) {
  return (
    <div className="overflow-hidden rounded-full border border-white/8 bg-white/[0.03]">
      <div
        className="h-1.5 rounded-full bg-gradient-to-r from-accent/35 via-accent to-white/75 transition-[width] duration-500"
        style={{ width: `${Math.max(percent, 6)}%` }}
      />
    </div>
  );
}

function stageStatusClass(status: string) {
  switch (status) {
    case "completed":
      return "border-emerald-400/20 bg-emerald-400/8 text-emerald-50";
    case "in_progress":
      return "border-sky-300/20 bg-sky-300/10 text-sky-50";
    case "failed":
      return "border-rose-400/20 bg-rose-400/10 text-rose-50";
    case "skipped":
      return "border-white/10 bg-white/[0.04] text-foreground/76";
    default:
      return "border-white/8 bg-black/30 text-muted-foreground";
  }
}

export function JobCard({ card, index, onReuse }: JobCardProps) {
  const [showDiagnostics, setShowDiagnostics] = useState(index === 0);
  const meta = phaseMeta(card.phase);
  const classification = useMemo(() => getClassificationSignals(card), [card]);
  const lowConfidence =
    classification && typeof classification.low_confidence === "boolean"
      ? classification.low_confidence
      : false;
  const timingEntries = useMemo(() => getTimingEntries(card), [card]);
  const languageSummary = useMemo(() => getLanguageSummary(card), [card]);
  const resultFacts = useMemo(() => getResultFacts(card), [card]);
  const progress = useMemo(() => getProgressSummary(card), [card]);
  const stageEntries = useMemo(() => getStageEntries(card), [card]);

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: -28, scale: 0.985 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 18, scale: 0.99 }}
      transition={{ duration: 0.34, ease: [0.2, 0.8, 0.2, 1] }}
      className="group relative overflow-hidden rounded-[34px] border border-white/10 bg-card/80 p-5 shadow-float"
    >
      <div className="pointer-events-none absolute inset-x-0 top-0 h-24 bg-[radial-gradient(circle_at_top,rgba(128,203,255,0.12),transparent_65%)] opacity-80" />

      <div className="relative flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <Badge variant={meta.variant}>
              {meta.icon}
              {meta.label}
            </Badge>
            <Badge variant="neutral">
              <FileText className="h-3.5 w-3.5" />
              {card.payload.source}
            </Badge>
            {lowConfidence ? <Badge variant="warning">low confidence</Badge> : null}
          </div>
          <h3 className="text-xl font-medium tracking-[-0.03em] text-foreground">{card.title}</h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">{card.preview}</p>
        </div>

        <div className="flex flex-col items-end gap-2">
          <div className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs uppercase tracking-[0.16em] text-foreground/82">
            {progress.label} · {progress.percent}%
          </div>
          <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
            {formatClockTime(card.createdAt)}
          </div>
          <Button variant="panel" size="sm" type="button" onClick={() => onReuse(card)}>
            <CopyPlus className="h-3.5 w-3.5" />
            Reuse
          </Button>
        </div>
      </div>

      <div className="relative mt-5">
        <ProgressRail percent={progress.percent} />
      </div>

      {stageEntries.length > 0 ? (
        <div className="relative mt-3 flex flex-wrap gap-2">
          {stageEntries.map((stage) => (
            <div
              key={`${card.localId}-${stage.name}-${stage.status}`}
              className={cn(
                "rounded-full border px-3 py-1.5 text-[11px] uppercase tracking-[0.16em]",
                stageStatusClass(stage.status),
              )}
            >
              {stage.label}
            </div>
          ))}
        </div>
      ) : null}

      {(card.phase === "queued" || card.phase === "processing") && card.status?.current_stage ? (
        <div className="mt-3 text-sm text-muted-foreground">
          Текущий этап: <span className="text-foreground">{card.status.stage_label ?? card.status.current_stage}</span>
        </div>
      ) : null}

      {card.phase === "failed" ? (
        <div className="relative mt-5 rounded-[24px] border border-rose-400/20 bg-rose-400/8 p-4">
          <div className="text-sm font-medium text-rose-100">{card.error?.message ?? "Request failed."}</div>
          {card.error?.code ? (
            <div className="mt-2 text-xs uppercase tracking-[0.16em] text-rose-100/70">
              {card.error.code}
            </div>
          ) : null}
        </div>
      ) : null}

      {card.phase === "completed" && card.result ? (
        <div className="relative mt-5 grid gap-5 xl:grid-cols-[minmax(0,1.1fr),minmax(320px,0.9fr)]">
          <div className="rounded-[28px] border border-white/8 bg-white/[0.025] p-4">
            <div className="mb-4 flex flex-wrap items-center gap-3">
              <div>
                <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  top category
                </div>
                <div className="mt-1 text-2xl font-medium tracking-[-0.04em] text-foreground">
                  {card.result.category.label}
                </div>
              </div>
              <Badge variant="neutral">
                <ArrowUpRight className="h-3.5 w-3.5" />
                score {formatScore(card.result.category.score)}
              </Badge>
            </div>

            <div className="grid gap-2">
              {card.result.tags.map((tag) => (
                <div
                  key={`${card.localId}-${tag.normalized_label}`}
                  className="rounded-[20px] border border-white/10 bg-black/30 px-3 py-3"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="text-sm font-medium text-foreground/92">{tag.label}</div>
                    <Badge variant="neutral">{tag.source}</Badge>
                    {typeof tag.confidence === "number" ? (
                      <Badge variant="neutral">conf {formatScore(tag.confidence)}</Badge>
                    ) : null}
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {tag.canonical_name ?? tag.normalized_label} · {tag.method}
                  </div>
                  {tag.reason ? (
                    <div className="mt-2 text-sm leading-6 text-muted-foreground">{tag.reason}</div>
                  ) : null}
                </div>
              ))}
            </div>

            {card.result.explanation ? (
              <p className="mt-4 text-sm leading-6 text-muted-foreground">{card.result.explanation}</p>
            ) : null}
          </div>

          <div className="rounded-[28px] border border-white/8 bg-white/[0.025] p-4">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  diagnostics
                </div>
                <div className="mt-1 text-sm text-foreground">Signals, timings and confidence</div>
              </div>
              <button
                type="button"
                onClick={() => setShowDiagnostics((current) => !current)}
                className="inline-flex items-center gap-2 rounded-full border border-white/10 px-3 py-1.5 text-xs uppercase tracking-[0.16em] text-muted-foreground transition hover:border-white/16 hover:text-foreground"
              >
                {showDiagnostics ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                {showDiagnostics ? "hide" : "show"}
              </button>
            </div>

            <div className="flex flex-wrap gap-2">
              {resultFacts.map((fact) => (
                <Badge key={fact.label} variant="neutral">
                  {fact.label}: {fact.value}
                </Badge>
              ))}
              {languageSummary ? <Badge variant="neutral">{languageSummary}</Badge> : null}
            </div>

            {showDiagnostics ? (
              <div className="mt-4 grid gap-4">
                <div>
                  <div className="mb-2 flex items-center gap-2 text-xs uppercase tracking-[0.16em] text-muted-foreground">
                    <Tags className="h-3.5 w-3.5" />
                    timings
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {timingEntries.length > 0 ? (
                      timingEntries.map((entry) => (
                        <div
                          key={entry.key}
                          className="rounded-[18px] border border-white/8 bg-black/30 px-3 py-2 text-sm text-foreground/84"
                        >
                          <span className="text-muted-foreground">{entry.key}</span> · {entry.value}
                        </div>
                      ))
                    ) : (
                      <div className="rounded-[18px] border border-white/8 bg-black/30 px-3 py-2 text-sm text-muted-foreground">
                        No timing signals returned.
                      </div>
                    )}
                  </div>
                </div>

                <div>
                  <div className="mb-2 text-xs uppercase tracking-[0.16em] text-muted-foreground">
                    stage flow
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {stageEntries.map((stage) => (
                      <div
                        key={`${card.localId}-details-${stage.name}-${stage.status}`}
                        className={cn(
                          "rounded-[18px] border px-3 py-2 text-sm",
                          stageStatusClass(stage.status),
                        )}
                      >
                        {stage.label}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="grid gap-2 text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  <div>
                    created {formatCompactDateTime(card.status?.created_at ?? null) ?? "n/a"}
                  </div>
                  <div>
                    finished {formatCompactDateTime(card.status?.finished_at ?? null) ?? "n/a"}
                  </div>
                  <div>job {card.jobId ?? "pending id"}</div>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </motion.article>
  );
}
