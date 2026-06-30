import { motion } from 'framer-motion'
import { GitMerge, Layers, Users, Zap } from 'lucide-react'
import type { RunResult } from '@/lib/types'

const STAGE_ORDER = ['extract', 'normalize', 'resolve', 'merge', 'validate']

function Stat({
  icon: Icon,
  value,
  label,
}: {
  icon: typeof Layers
  value: string | number
  label: string
}) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-secondary text-muted-foreground">
        <Icon className="size-4" />
      </div>
      <div className="leading-tight">
        <div className="text-[19px] font-semibold tracking-[-0.01em] tabular-nums">
          {value}
        </div>
        <div className="text-[11px] uppercase tracking-wide text-muted-foreground/70">
          {label}
        </div>
      </div>
    </div>
  )
}

export function StatsStrip({ result }: { result: RunResult }) {
  const { stats, timings_ms } = result
  const total = STAGE_ORDER.filter((k) => k in timings_ms).reduce(
    (sum, k) => sum + timings_ms[k],
    0,
  )
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="flex flex-wrap items-center gap-x-8 gap-y-4 rounded-2xl border border-border/70 bg-card px-6 py-4 shadow-[0_1px_2px_rgba(0,0,0,0.04)]"
    >
      <Stat icon={Layers} value={stats.records_in} label="records in" />
      <Stat icon={Users} value={stats.clusters_out} label="candidates" />
      <Stat icon={GitMerge} value={stats.conflicts_found} label="conflicts" />
      <Stat icon={Zap} value={`${total.toFixed(0)} ms`} label="pipeline" />
      <div className="ml-auto hidden items-center gap-1.5 lg:flex">
        {STAGE_ORDER.filter((k) => k in timings_ms).map((k) => (
          <span
            key={k}
            className="rounded-full bg-secondary px-2.5 py-1 font-mono text-[11px] text-muted-foreground"
          >
            {k} {timings_ms[k].toFixed(1)}
          </span>
        ))}
      </div>
    </motion.div>
  )
}
