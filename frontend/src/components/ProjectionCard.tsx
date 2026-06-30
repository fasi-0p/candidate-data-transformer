import { useState } from 'react'
import { Check, Copy, FileOutput, Loader2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { ProjectionSummary } from '@/lib/types'

export function ProjectionCard({
  projections,
  selected,
  onSelect,
  onApply,
  applying,
  output,
}: {
  projections: ProjectionSummary[]
  selected: string
  onSelect: (id: string) => void
  onApply: () => void
  applying: boolean
  output: unknown[] | null
}) {
  const [copied, setCopied] = useState(false)
  const json = output ? JSON.stringify(output, null, 2) : ''
  const active = projections.find((p) => p.id === selected)

  const copy = async () => {
    await navigator.clipboard.writeText(json)
    setCopied(true)
    setTimeout(() => setCopied(false), 1400)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <span className="flex size-6 items-center justify-center rounded-full bg-primary/10 text-[12px] font-semibold text-primary">
            3
          </span>
          Projection
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-[13px] leading-relaxed text-muted-foreground">
          The canonical model is never modified — a projection only reshapes a
          copy into your output schema.
        </p>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1 space-y-1.5">
            <Label htmlFor="projection-select">Output schema</Label>
            <Select value={selected} onValueChange={onSelect}>
              <SelectTrigger id="projection-select">
                <SelectValue placeholder="Choose a schema…" />
              </SelectTrigger>
              <SelectContent>
                {projections.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button onClick={onApply} disabled={applying || !selected}>
            {applying ? (
              <>
                <Loader2 className="animate-spin" /> Projecting…
              </>
            ) : (
              <>
                <FileOutput /> Apply
              </>
            )}
          </Button>
        </div>

        {active && (
          <div className="flex flex-wrap gap-1.5">
            {active.fields.map((f) => (
              <Badge key={f} variant="outline" className="font-mono">
                {f}
              </Badge>
            ))}
          </div>
        )}

        {output && (
          <div className="relative">
            <Button
              variant="ghost"
              size="sm"
              onClick={copy}
              className="absolute right-2 top-2 z-10 h-7 gap-1.5 px-2.5 text-muted-foreground"
            >
              {copied ? (
                <>
                  <Check className="text-[var(--color-success)]" /> Copied
                </>
              ) : (
                <>
                  <Copy /> Copy
                </>
              )}
            </Button>
            <pre className="max-h-[30rem] overflow-auto rounded-xl border border-border/70 bg-[oklch(0.985_0.002_270)] p-4 font-mono text-[12.5px] leading-relaxed text-foreground/90">
              {json}
            </pre>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
