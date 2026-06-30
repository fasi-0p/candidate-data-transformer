import { Badge } from '@/components/ui/badge'
import { ConfidenceBar } from './ConfidenceBar'
import type { Tracked } from '@/lib/types'
import type { LucideIcon } from 'lucide-react'

// Skills are many short tags, so a row-per-skill (each with its own confidence
// bar) is noisy. Instead we render the whole set as one chip list with a single
// aggregate confidence — the mean across skills — while each chip keeps its own
// source + score on hover so provenance is never lost.
export function SkillsRow({
  label,
  icon: Icon,
  items,
}: {
  label: string
  icon: LucideIcon
  items: Tracked<string>[] | null | undefined
}) {
  const list = items ?? []
  const avg = list.length
    ? list.reduce((sum, t) => sum + t.confidence, 0) / list.length
    : 0
  const sources = Array.from(
    new Set(list.flatMap((t) => t.sources ?? [t.source])),
  )

  return (
    <div className="grid grid-cols-[140px_1fr] gap-x-4 gap-y-0 px-5 py-1 sm:grid-cols-[160px_1fr]">
      <div className="flex items-center gap-2 pt-3.5 text-[13px] font-medium text-muted-foreground">
        <Icon className="size-3.5 shrink-0 text-muted-foreground/60" />
        {label}
      </div>
      <div className="min-w-0 py-2.5">
        {list.length === 0 ? (
          <div className="text-[15px] text-muted-foreground/50">—</div>
        ) : (
          <>
            <div className="mb-2.5 flex flex-wrap items-center gap-x-3 gap-y-1">
              <ConfidenceBar value={avg} />
              <span className="text-[11px] text-muted-foreground/70">
                {list.length} skill{list.length === 1 ? '' : 's'}
                {sources.length > 0 && <> · {sources.join(', ')}</>}
              </span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {list.map((t, i) => (
                <Badge
                  key={i}
                  variant={t.malformed ? 'warning' : 'default'}
                  title={`${t.source} · ${Math.round(t.confidence * 100)}/100${
                    t.malformed ? ' · unverified' : ''
                  }`}
                >
                  {t.value}
                </Badge>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
