import { confidenceTone } from '@/lib/format'
import { cn } from '@/lib/utils'

const TONE: Record<string, { bar: string; text: string }> = {
  high: { bar: 'bg-[var(--color-success)]', text: 'text-[var(--color-success)]' },
  mid: { bar: 'bg-[var(--color-warning)]', text: 'text-[oklch(0.52_0.14_70)]' },
  low: { bar: 'bg-destructive', text: 'text-destructive' },
}

export function ConfidenceBar({
  value,
  className,
}: {
  value: number
  className?: string
}) {
  const tone = TONE[confidenceTone(value)]
  const pct = Math.round(value * 100)
  return (
    <div className={cn('flex items-center gap-2', className)}>
      <div className="h-1 w-14 overflow-hidden rounded-full bg-secondary">
        <div
          className={cn('h-full rounded-full transition-all', tone.bar)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span
        className={cn(
          'flex w-9 items-baseline justify-end gap-px font-mono tabular-nums',
          tone.text,
        )}
      >
        <span className="text-[12px] font-medium">{Math.round(value * 100)}</span>
        <span className="text-[9px] opacity-50">/100</span>
      </span>
    </div>
  )
}
