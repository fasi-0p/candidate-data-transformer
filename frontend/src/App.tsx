import { useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertCircle, Boxes, ScanLine, ShieldCheck, Workflow, X } from 'lucide-react'
import { TooltipProvider } from '@/components/ui/tooltip'
import { CandidateCard } from '@/components/CandidateCard'
import { ProjectionCard } from '@/components/ProjectionCard'
import { StatsStrip } from '@/components/StatsStrip'
import { UploadCard } from '@/components/UploadCard'
import {
  applyProjection,
  fetchProjections,
  runPipeline,
  type RunInput,
} from '@/lib/api'
import type { ProjectionSummary, RunResult } from '@/lib/types'

const EMPTY_INPUT: RunInput = {
  csv: [],
  resume: [],
  ats: [],
  notes: [],
  github: '',
  linkedin: '',
}

function App() {
  const [input, setInput] = useState<RunInput>(EMPTY_INPUT)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<RunResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [projections, setProjections] = useState<ProjectionSummary[]>([])
  const [selectedProjection, setSelectedProjection] = useState('')
  const [applying, setApplying] = useState(false)
  const [output, setOutput] = useState<unknown[] | null>(null)

  useEffect(() => {
    fetchProjections()
      .then((ps) => {
        setProjections(ps)
        if (ps.length) setSelectedProjection(ps[0].id)
      })
      .catch(() => {
        /* engine offline — projection panel just stays empty */
      })
  }, [])

  const reportById = useMemo(() => {
    const map: Record<string, RunResult['validation'][number]> = {}
    for (const r of result?.validation ?? []) map[r.candidate_id] = r
    return map
  }, [result])

  const orderedCandidates = useMemo(() => {
    if (!result) return []
    return [...result.candidates].sort(
      (a, b) =>
        b.record_confidence - a.record_confidence ||
        a.candidate_id.localeCompare(b.candidate_id),
    )
  }, [result])

  async function handleRun() {
    setRunning(true)
    setError(null)
    setOutput(null)
    try {
      const data = await runPipeline(input)
      setResult(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setResult(null)
    } finally {
      setRunning(false)
    }
  }

  async function handleApply() {
    if (!result || !selectedProjection) return
    setApplying(true)
    try {
      const out = await applyProjection(result.run_id, selectedProjection)
      setOutput(out)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setApplying(false)
    }
  }

  return (
    <TooltipProvider>
      <div className="relative min-h-screen overflow-x-hidden">
        <div className="aurora" aria-hidden />

        <main className="relative mx-auto w-full max-w-3xl px-5 pb-28 pt-16 sm:px-6">
          {/* hero */}
          <motion.header
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
            className="mb-12 text-center"
          >
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-border/70 bg-card/70 px-3.5 py-1.5 text-[12px] font-medium text-muted-foreground backdrop-blur">
              <Workflow className="size-3.5 text-primary" />
              Deterministic · Explainable · Configurable
            </div>
            <h1 className="text-balance text-[34px] font-semibold leading-[1.1] tracking-[-0.025em] sm:text-[44px]">
              Candidate Data
              <br />
              <span className="text-muted-foreground/80">Transformation Engine</span>
            </h1>
            <p className="mx-auto mt-4 max-w-md text-pretty text-[15px] leading-relaxed text-muted-foreground">
              Consolidate heterogeneous sources into one canonical profile —
              every field traceable to its source, conflict, and confidence.
            </p>

            <div className="mt-7 flex items-center justify-center gap-6 text-[12px] text-muted-foreground/80">
              <span className="flex items-center gap-1.5">
                <ScanLine className="size-3.5 text-primary/70" /> Provenance
              </span>
              <span className="flex items-center gap-1.5">
                <ShieldCheck className="size-3.5 text-primary/70" /> Confidence
              </span>
              <span className="flex items-center gap-1.5">
                <Boxes className="size-3.5 text-primary/70" /> Projection
              </span>
            </div>
          </motion.header>

          <div className="space-y-6">
            <UploadCard
              value={input}
              onChange={setInput}
              onRun={handleRun}
              running={running}
            />

            <AnimatePresence>
              {error && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="flex items-start gap-3 rounded-2xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive"
                >
                  <AlertCircle className="mt-0.5 size-4 shrink-0" />
                  <span className="flex-1">{error}</span>
                  <button
                    onClick={() => setError(null)}
                    className="shrink-0 rounded-md p-0.5 hover:bg-destructive/10"
                    aria-label="Dismiss"
                  >
                    <X className="size-4" />
                  </button>
                </motion.div>
              )}
            </AnimatePresence>

            {result && (
              <>
                <StatsStrip result={result} />

                <section className="space-y-4">
                  <div className="flex items-baseline justify-between px-1">
                    <h2 className="flex items-center gap-2 text-[15px] font-semibold tracking-[-0.01em]">
                      <span className="flex size-6 items-center justify-center rounded-full bg-primary/10 text-[12px] font-semibold text-primary">
                        2
                      </span>
                      Canonical inspector
                    </h2>
                    <span className="text-[12px] text-muted-foreground/70">
                      {orderedCandidates.length} profile
                      {orderedCandidates.length === 1 ? '' : 's'} · expand a field
                      for provenance
                    </span>
                  </div>
                  <div className="space-y-4">
                    {orderedCandidates.map((c, i) => (
                      <CandidateCard
                        key={c.candidate_id}
                        candidate={c}
                        report={reportById[c.candidate_id]}
                        index={i}
                      />
                    ))}
                  </div>
                </section>

                <ProjectionCard
                  projections={projections}
                  selected={selectedProjection}
                  onSelect={setSelectedProjection}
                  onApply={handleApply}
                  applying={applying}
                  output={output}
                />
              </>
            )}
          </div>

          <footer className="mt-16 text-center text-[12px] text-muted-foreground/50">
            Multi-Source Candidate Data Transformer — pure engine, thin UI.
          </footer>
        </main>
      </div>
    </TooltipProvider>
  )
}

export default App
