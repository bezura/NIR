import { useMemo, useRef } from "react";
import { Database, FileUp, LoaderCircle, Sparkles, Wand2 } from "lucide-react";

import type { DemoPreset } from "../lib/demo-presets";
import type { LlmStrategy, OutputLanguage, RequestDraft, SourceType, TaggingMode } from "../types/tagging";
import { cn } from "../lib/utils";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Switch } from "./ui/switch";
import { Textarea } from "./ui/textarea";

const SOURCE_OPTIONS: { value: SourceType; label: string }[] = [
  { value: "note", label: "Note" },
  { value: "snippet", label: "Snippet" },
  { value: "web_page", label: "Web" },
  { value: "article", label: "Article" },
  { value: "document", label: "Document" },
];

const TAGGING_MODE_OPTIONS: { value: TaggingMode; label: string; hint: string }[] = [
  { value: "generate", label: "Generate", hint: "Новые теги из текста" },
  { value: "hybrid", label: "Hybrid", hint: "Модель + каталог" },
  { value: "existing_only", label: "Existing only", hint: "Только из existing_tags" },
  { value: "curated_only", label: "Curated only", hint: "Только из curated_tags" },
];

const OUTPUT_LANGUAGE_OPTIONS: { value: OutputLanguage; label: string }[] = [
  { value: "auto", label: "Auto" },
  { value: "ru", label: "RU" },
  { value: "en", label: "EN" },
];

const LLM_STRATEGY_OPTIONS: { value: LlmStrategy; label: string; hint: string }[] = [
  { value: "disabled", label: "Disabled", hint: "Только baseline pipeline" },
  { value: "low_confidence_only", label: "Low confidence", hint: "LLM только для спорных кейсов" },
  { value: "always", label: "Always", hint: "LLM после каждого run" },
];

type ApiStatus = "unknown" | "checking" | "online" | "offline";

interface ComposerPanelProps {
  draft: RequestDraft;
  presets: DemoPreset[];
  isSubmitting: boolean;
  submitError: string | null;
  apiStatus: ApiStatus;
  onChange(next: Partial<RequestDraft>): void;
  onSubmit(): void;
  onApplyPreset(preset: DemoPreset): void;
  onPingApi(): void;
  onLoadFile(file: File): void;
}

function apiStatusLabel(status: ApiStatus) {
  switch (status) {
    case "checking":
      return { text: "checking", variant: "active" as const };
    case "online":
      return { text: "local api online", variant: "success" as const };
    case "offline":
      return { text: "api not reachable", variant: "danger" as const };
    default:
      return { text: "endpoint unknown", variant: "neutral" as const };
  }
}

function optionButton(active: boolean) {
  return cn(
    "rounded-[18px] border px-3 py-2 text-left transition duration-200",
    active
      ? "border-accent/40 bg-accent/12 text-foreground"
      : "border-white/8 bg-white/[0.025] text-muted-foreground hover:border-white/14 hover:text-foreground",
  );
}

export function ComposerPanel({
  draft,
  presets,
  isSubmitting,
  submitError,
  apiStatus,
  onChange,
  onSubmit,
  onApplyPreset,
  onPingApi,
  onLoadFile,
}: ComposerPanelProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const apiBadge = useMemo(() => apiStatusLabel(apiStatus), [apiStatus]);

  return (
    <section>
      <div className="liquid-glass rounded-[34px] border border-white/10 bg-card/72 p-5 shadow-panel md:p-6">
        <div className="mb-6 flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <Badge variant="neutral" className="mb-3 w-fit">
              <Sparkles className="h-3.5 w-3.5" />
              live request composer
            </Badge>
            <h1 className="text-[2rem] font-medium tracking-[-0.04em] text-foreground">
              Request <span className="font-serif text-[2.1rem] italic font-normal">flow</span>
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
              Подготовь поля запроса, отправь их в локальный tagging API и смотри, как каждая задача
              разворачивается в отдельной карточке потока.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr),auto] xl:min-w-[440px]">
            <Input
              value={draft.apiBaseUrl}
              onChange={(event) => onChange({ apiBaseUrl: event.target.value })}
              placeholder="/api/v1/tagging"
            />
            <div className="flex items-center justify-end gap-3">
              <Badge variant={apiBadge.variant} className="w-fit">
                <Database className="h-3.5 w-3.5" />
                {apiBadge.text}
              </Badge>
              <Button variant="panel" size="sm" type="button" onClick={onPingApi}>
                Проверить
              </Button>
            </div>
          </div>
        </div>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.55fr),minmax(340px,0.95fr)]">
          <section className="rounded-[28px] border border-white/8 bg-white/[0.02] p-4">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground">request body</div>
                <div className="mt-1 text-sm text-foreground">Основной текст и вид документа</div>
              </div>

              <Button
                variant="panel"
                size="sm"
                type="button"
                onClick={() => fileInputRef.current?.click()}
              >
                <FileUp className="h-3.5 w-3.5" />
                Загрузить text
              </Button>
            </div>

            <input
              ref={fileInputRef}
              type="file"
              accept=".txt,.md"
              className="hidden"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) {
                  onLoadFile(file);
                }
                event.target.value = "";
              }}
            />

            <div className="mb-4">
              <div className="mb-2 text-xs uppercase tracking-[0.16em] text-muted-foreground">source</div>
              <div className="grid grid-cols-2 gap-2 lg:grid-cols-5">
                {SOURCE_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => onChange({ source: option.value })}
                    className={cn(
                      "rounded-full border px-3 py-2 text-sm transition duration-200",
                      draft.source === option.value
                        ? "border-accent/40 bg-accent/12 text-foreground"
                        : "border-white/8 bg-white/[0.025] text-muted-foreground hover:border-white/14 hover:text-foreground",
                    )}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid gap-3 xl:grid-cols-[minmax(0,0.95fr),minmax(0,1.7fr)]">
              <div className="grid gap-3">
                <Input
                  value={draft.title}
                  onChange={(event) => onChange({ title: event.target.value })}
                  placeholder="Optional title"
                />
                <div className="grid gap-3 sm:grid-cols-2">
                  <Input
                    value={draft.language}
                    onChange={(event) => onChange({ language: event.target.value })}
                    placeholder="Language: ru / en / mixed"
                  />
                  <Input
                    value={draft.collection}
                    onChange={(event) => onChange({ collection: event.target.value })}
                    placeholder="Collection or source group"
                  />
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Input
                    value={draft.author}
                    onChange={(event) => onChange({ author: event.target.value })}
                    placeholder="Author or team"
                  />
                  <Input
                    value={draft.keywords}
                    onChange={(event) => onChange({ keywords: event.target.value })}
                    placeholder="Keywords через запятую"
                  />
                </div>
              </div>

              <Textarea
                value={draft.text}
                onChange={(event) => onChange({ text: event.target.value })}
                placeholder="Paste document text here"
                className="min-h-[280px]"
              />
            </div>
          </section>

          <div className="grid gap-5">
            <section className="rounded-[28px] border border-white/8 bg-white/[0.02] p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <div>
                  <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground">presets</div>
                  <div className="mt-1 text-sm text-foreground">Quick real-world inputs</div>
                </div>
              </div>

              <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
                {presets.map((preset) => (
                  <button
                    key={preset.id}
                    type="button"
                    onClick={() => onApplyPreset(preset)}
                    className="group rounded-[24px] border border-white/8 bg-white/[0.025] px-4 py-3 text-left transition duration-200 hover:border-white/14 hover:bg-white/[0.05]"
                  >
                    <div className="flex items-center justify-between gap-4">
                      <div>
                        <div className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                          {preset.eyebrow}
                        </div>
                        <div className="mt-1 text-sm font-medium text-foreground">{preset.label}</div>
                      </div>
                      <Wand2 className="h-4 w-4 text-muted-foreground transition group-hover:text-foreground" />
                    </div>
                  </button>
                ))}
              </div>
            </section>

            <section className="rounded-[28px] border border-white/8 bg-white/[0.02] p-4">
              <div className="mb-4 text-xs uppercase tracking-[0.16em] text-muted-foreground">options</div>

              <div className="flex items-center justify-between gap-4 rounded-[24px] border border-white/8 bg-black/30 px-4 py-3">
                <div>
                  <div className="text-sm text-foreground">Rules engine</div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    Правила и metadata-hints влияют на бусты и итоговые теги.
                  </div>
                </div>
                <Switch
                  checked={draft.enableRules}
                  onCheckedChange={(checked) => onChange({ enableRules: checked })}
                />
              </div>

              <div className="mt-3 flex items-center justify-between gap-4 rounded-[24px] border border-white/8 bg-black/30 px-4 py-3">
                <div>
                  <div className="text-sm text-foreground">Max tags</div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    Сейчас сервис принимает значения от 1 до 10.
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    variant="subtle"
                    size="sm"
                    type="button"
                    onClick={() => onChange({ maxTags: Math.max(1, draft.maxTags - 1) })}
                  >
                    -
                  </Button>
                  <div className="w-10 text-center text-lg font-semibold tabular-nums text-foreground">
                    {draft.maxTags}
                  </div>
                  <Button
                    variant="subtle"
                    size="sm"
                    type="button"
                    onClick={() => onChange({ maxTags: Math.min(10, draft.maxTags + 1) })}
                  >
                    +
                  </Button>
                </div>
              </div>

              <div className="mt-3 rounded-[24px] border border-white/8 bg-black/30 p-4">
                <div className="mb-3">
                  <div className="text-sm text-foreground">Tagging mode</div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    Соответствует `options.tagging_mode` в job API.
                  </div>
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  {TAGGING_MODE_OPTIONS.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => onChange({ taggingMode: option.value })}
                      className={optionButton(draft.taggingMode === option.value)}
                    >
                      <div className="text-sm font-medium">{option.label}</div>
                      <div className="mt-1 text-xs text-muted-foreground">{option.hint}</div>
                    </button>
                  ))}
                </div>
              </div>

              <div className="mt-3 rounded-[24px] border border-white/8 bg-black/30 p-4">
                <div className="mb-3 flex items-center justify-between gap-4">
                  <div>
                    <div className="text-sm text-foreground">Output language</div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      Локализация rule-based и catalog тегов.
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {OUTPUT_LANGUAGE_OPTIONS.map((option) => (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => onChange({ outputLanguage: option.value })}
                        className={cn(
                          "rounded-full border px-3 py-1.5 text-xs uppercase tracking-[0.16em] transition",
                          draft.outputLanguage === option.value
                            ? "border-accent/40 bg-accent/12 text-foreground"
                            : "border-white/8 bg-white/[0.025] text-muted-foreground hover:border-white/14 hover:text-foreground",
                        )}
                      >
                        {option.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div className="mt-3 rounded-[24px] border border-white/8 bg-black/30 p-4">
                <div className="mb-3">
                  <div className="text-sm text-foreground">LLM strategy</div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    Предпочтительный способ запускать enhancer в текущем API.
                  </div>
                </div>
                <div className="grid gap-2">
                  {LLM_STRATEGY_OPTIONS.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => onChange({ llmStrategy: option.value })}
                      className={optionButton(draft.llmStrategy === option.value)}
                    >
                      <div className="text-sm font-medium">{option.label}</div>
                      <div className="mt-1 text-xs text-muted-foreground">{option.hint}</div>
                    </button>
                  ))}
                </div>
              </div>

              <div className="mt-3 flex items-center justify-between gap-4 rounded-[24px] border border-white/8 bg-black/30 px-4 py-3">
                <div>
                  <div className="text-sm text-foreground">Legacy LLM toggle</div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    Сохраняется для обратной совместимости через `use_llm_postprocess`.
                  </div>
                </div>
                <Switch
                  checked={draft.useLlmPostprocess}
                  onCheckedChange={(checked) => onChange({ useLlmPostprocess: checked })}
                />
              </div>

              {submitError ? (
                <div className="mt-4 rounded-[24px] border border-rose-400/20 bg-rose-400/8 px-4 py-3 text-sm text-rose-100">
                  {submitError}
                </div>
              ) : null}

              <Button className="mt-4 w-full" size="lg" type="button" onClick={onSubmit} disabled={isSubmitting}>
                {isSubmitting ? <LoaderCircle className="h-4 w-4 animate-spin" /> : null}
                {isSubmitting ? "Отправка..." : "Отправить в tagging API"}
              </Button>
            </section>
          </div>
        </div>
      </div>
    </section>
  );
}
