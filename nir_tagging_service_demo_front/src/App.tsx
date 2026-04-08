import { Activity, CheckCheck, Layers3, ShieldAlert } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";

import { ComposerPanel } from "./components/composer-panel";
import { JobCard } from "./components/job-card";
import { Badge } from "./components/ui/badge";
import { useTaggingStream } from "./hooks/use-tagging-stream";

function MetricPill({
  label,
  value,
  icon,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-full border border-white/10 bg-white/[0.03] px-4 py-2.5">
      <div className="flex items-center gap-2 text-xs uppercase tracking-[0.16em] text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className="mt-1 text-lg font-semibold tabular-nums text-foreground">{value}</div>
    </div>
  );
}

export default function App() {
  const {
    draft,
    cards,
    stats,
    presets,
    apiStatus,
    isSubmitting,
    submitError,
    setDraft,
    applyPreset,
    submit,
    reuseCard,
    loadFile,
    pingApi,
  } = useTaggingStream();

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <video
          autoPlay
          muted
          loop
          playsInline
          className="absolute inset-0 h-full w-full object-cover"
          src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260330_145725_08886141-ed95-4a8e-8d6d-b75eaadce638.mp4"
        />
        <div className="absolute inset-0 bg-black/72" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.08),transparent_36%)]" />
        <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(0,0,0,0.35),rgba(0,0,0,0.78))]" />
      </div>

      <div className="relative mx-auto max-w-[1520px] px-4 pb-10 pt-6 md:px-6 xl:px-8">
        <header className="mb-6 rounded-[34px] border border-white/10 bg-white/[0.025] p-5 shadow-panel">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <Badge variant="neutral" className="mb-4 w-fit">
                nir tagging service
              </Badge>
              <h1 className="text-4xl font-medium tracking-[-0.06em] text-foreground md:text-6xl">
                Living <span className="font-serif italic font-normal">request stream</span>
              </h1>
              <p className="mt-4 max-w-2xl text-base leading-7 text-muted-foreground md:text-lg">
                Не лендинг, а рабочий экран: каждая отправка превращается в самостоятельную
                карточку, под ней видно прогресс, итоговую категорию, теги и внутренние сигналы
                пайплайна.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <MetricPill label="total" value={stats.total} icon={<Layers3 className="h-3.5 w-3.5" />} />
              <MetricPill label="active" value={stats.active} icon={<Activity className="h-3.5 w-3.5" />} />
              <MetricPill label="completed" value={stats.completed} icon={<CheckCheck className="h-3.5 w-3.5" />} />
              <MetricPill label="failed" value={stats.failed} icon={<ShieldAlert className="h-3.5 w-3.5" />} />
            </div>
          </div>
        </header>

        <main className="grid gap-6">
          <ComposerPanel
            draft={draft}
            presets={presets}
            isSubmitting={isSubmitting}
            submitError={submitError}
            apiStatus={apiStatus}
            onChange={(next) => setDraft((current) => ({ ...current, ...next }))}
            onSubmit={submit}
            onApplyPreset={applyPreset}
            onPingApi={pingApi}
            onLoadFile={loadFile}
          />

          <section className="min-w-0">
            <div className="mb-4 flex flex-col gap-3 rounded-[30px] border border-white/8 bg-white/[0.02] p-5 md:flex-row md:items-center md:justify-between">
              <div>
                <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground">stream</div>
                <div className="mt-1 text-xl font-medium tracking-[-0.03em] text-foreground">
                  Newest request always lands first
                </div>
              </div>
              <div className="max-w-lg text-sm leading-6 text-muted-foreground">
                Карточки анимированно перестраиваются при каждом новом запросе. Это удобно для
                ручного прогона кейсов и сравнения реальных ответов сервиса.
              </div>
            </div>

            {cards.length === 0 ? (
              <div className="liquid-glass flex min-h-[520px] items-center justify-center rounded-[36px] border border-dashed border-white/10 bg-card/55 p-8 text-center shadow-panel">
                <div className="max-w-xl">
                  <div className="mb-3 text-xs uppercase tracking-[0.18em] text-muted-foreground">
                    waiting for first request
                  </div>
                  <h2 className="text-3xl font-medium tracking-[-0.05em] text-foreground">
                    Подготовь текст слева и отправь его в локальный API.
                  </h2>
                  <p className="mt-4 text-sm leading-7 text-muted-foreground">
                    Можно выбрать готовый preset, вставить свой документ, загрузить `.txt`/`.md`
                    и сразу увидеть полный цикл от `queued` до финального result.
                  </p>
                </div>
              </div>
            ) : (
              <motion.div layout className="space-y-4">
                <AnimatePresence initial={false}>
                  {cards.map((card, index) => (
                    <JobCard key={card.localId} card={card} index={index} onReuse={reuseCard} />
                  ))}
                </AnimatePresence>
              </motion.div>
            )}
          </section>
        </main>
      </div>
    </div>
  );
}
