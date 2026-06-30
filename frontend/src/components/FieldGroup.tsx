import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { Badge } from '@/components/ui/badge'
import { ConfidenceBar } from './ConfidenceBar'
import { formatValue } from '@/lib/format'
import type { Tracked } from '@/lib/types'
import { cn } from '@/lib/utils'
import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

type Fmt = (v: unknown) => string

function SourceChip({ source, extra }: { source: string; extra: number }) {
  return (
    <span className="shrink-0 rounded-md bg-secondary px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
      {source}
      {extra > 0 && <span className="text-primary"> +{extra}</span>}
    </span>
  )
}

// Every value is expandable so its provenance is always one click away — even a
// single-source field reveals where it came from and how it was extracted.
function ValueRow({ t, fmt }: { t: Tracked; fmt: Fmt }) {
  const conflicts = t.conflicts ?? []
  const allSources = t.sources ?? [t.source]
  const corroborators = allSources.filter((s) => s !== t.source)

  return (
    <Accordion type="single" collapsible>
      <AccordionItem value="v" className="border-b-0">
        <AccordionTrigger className="items-start gap-2.5 py-2.5">
          <span className="min-w-0 flex-1 break-words pt-0.5 text-[15px] leading-snug text-foreground">
            {fmt(t.value)}
          </span>
          {/* Provenance cluster is pinned right and never shrinks, so the
              confidence bar stays visible no matter how long the value is — a
              long value wraps to the next line instead of pushing the bar off. */}
          <span className="flex shrink-0 items-center gap-2">
            <SourceChip source={t.source} extra={corroborators.length} />
            {t.malformed && <Badge variant="warning">unverified</Badge>}
            {conflicts.length > 0 && (
              <Badge variant="destructive">conflict</Badge>
            )}
            <ConfidenceBar value={t.confidence} />
          </span>
        </AccordionTrigger>
        <AccordionContent>
          <dl className="space-y-1.5 rounded-xl bg-secondary/50 px-3.5 py-3 text-[13px]">
            <Line label="source">
              <span className="font-medium">{t.source}</span>{' '}
              <span className="text-muted-foreground/70">
                via {t.method}
              </span>
            </Line>
            {corroborators.length > 0 && (
              <Line label="agreed by" tone="success">
                {corroborators.join(', ')}
              </Line>
            )}
            {t.malformed && (
              <Line label="note" tone="warning">
                kept but could not be normalized — counted against confidence
              </Line>
            )}
            {conflicts.map((c, i) => (
              <Line key={i} label="conflict" tone="destructive">
                {formatValue(c.value)} from{' '}
                <span className="font-medium">{c.source}</span> lost
                <span className="text-muted-foreground/80"> — {c.reason}</span>
              </Line>
            ))}
          </dl>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  )
}

function Line({
  label,
  tone,
  children,
}: {
  label: string
  tone?: 'success' | 'warning' | 'destructive'
  children: ReactNode
}) {
  const toneClass = {
    success: 'text-[var(--color-success)]',
    warning: 'text-[oklch(0.52_0.14_70)]',
    destructive: 'text-destructive',
  }
  return (
    <div className="flex gap-2.5">
      <dt
        className={cn(
          'w-20 shrink-0 font-mono text-[11px] uppercase tracking-wide',
          tone ? toneClass[tone] : 'text-muted-foreground/60',
        )}
      >
        {label}
      </dt>
      <dd className="min-w-0 flex-1 text-foreground/90">{children}</dd>
    </div>
  )
}

export function FieldGroup({
  label,
  icon: Icon,
  items,
  fmt = formatValue,
}: {
  label: string
  icon: LucideIcon
  items: Tracked[] | null | undefined
  fmt?: Fmt
}) {
  const list = items ?? []
  return (
    <div className="grid grid-cols-[140px_1fr] gap-x-4 gap-y-0 px-5 py-1 sm:grid-cols-[160px_1fr]">
      <div className="flex items-center gap-2 pt-3.5 text-[13px] font-medium text-muted-foreground">
        <Icon className="size-3.5 shrink-0 text-muted-foreground/60" />
        {label}
      </div>
      <div className="min-w-0 divide-y divide-border/50">
        {list.length === 0 ? (
          <div className="flex items-center py-2.5 text-[15px] text-muted-foreground/50">
            —
          </div>
        ) : (
          list.map((t, i) => <ValueRow key={i} t={t} fmt={fmt} />)
        )}
      </div>
    </div>
  )
}
