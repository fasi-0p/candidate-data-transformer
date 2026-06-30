import { useId } from 'react'
import {
  ArrowRight,
  Database,
  FileJson,
  FileText,
  Fingerprint,
  GitBranch,
  Loader2,
  StickyNote,
  Upload,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { RunInput } from '@/lib/api'
import { cn } from '@/lib/utils'
import type { LucideIcon } from 'lucide-react'

function FileField({
  label,
  hint,
  icon: Icon,
  accept,
  files,
  onChange,
}: {
  label: string
  hint: string
  icon: LucideIcon
  accept: string
  files: File[]
  onChange: (files: File[]) => void
}) {
  const id = useId()
  const count = files.length
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>
        <Icon className="size-3.5 text-muted-foreground/70" />
        {label}
      </Label>
      <label
        htmlFor={id}
        className={cn(
          'group flex cursor-pointer items-center gap-3 rounded-xl border border-dashed border-input bg-card px-3.5 py-2.5 text-sm transition-colors hover:border-primary/50 hover:bg-accent/40',
          count > 0 && 'border-solid border-primary/40 bg-primary/[0.03]',
        )}
      >
        <Upload className="size-4 shrink-0 text-muted-foreground/60 transition-colors group-hover:text-primary" />
        <span className="min-w-0 flex-1 truncate text-muted-foreground">
          {count === 0
            ? hint
            : count === 1
              ? files[0].name
              : `${count} files selected`}
        </span>
        {count > 0 && (
          <span className="shrink-0 rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary">
            {count}
          </span>
        )}
      </label>
      <input
        id={id}
        type="file"
        accept={accept}
        multiple
        className="sr-only"
        onChange={(e) => onChange(Array.from(e.target.files ?? []))}
      />
    </div>
  )
}

export function UploadCard({
  value,
  onChange,
  onRun,
  running,
}: {
  value: RunInput
  onChange: (next: RunInput) => void
  onRun: () => void
  running: boolean
}) {
  const set = <K extends keyof RunInput>(key: K, v: RunInput[K]) =>
    onChange({ ...value, [key]: v })

  const hasInput =
    value.csv.length > 0 ||
    value.resume.length > 0 ||
    value.ats.length > 0 ||
    value.notes.length > 0 ||
    value.github.trim().length > 0

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <span className="flex size-6 items-center justify-center rounded-full bg-primary/10 text-[12px] font-semibold text-primary">
            1
          </span>
          Sources
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <FileField
            label="Recruiter CSV"
            hint="Drop or choose .csv"
            icon={FileText}
            accept=".csv"
            files={value.csv}
            onChange={(f) => set('csv', f)}
          />
          <FileField
            label="Resume"
            hint="Drop or choose .pdf"
            icon={FileText}
            accept=".pdf"
            files={value.resume}
            onChange={(f) => set('resume', f)}
          />
          <FileField
            label="ATS export"
            hint="Drop or choose .json"
            icon={FileJson}
            accept=".json"
            files={value.ats}
            onChange={(f) => set('ats', f)}
          />
          <FileField
            label="Recruiter notes"
            hint="Drop or choose .txt"
            icon={StickyNote}
            accept=".txt"
            files={value.notes}
            onChange={(f) => set('notes', f)}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="github-in">
              <GitBranch className="size-3.5 text-muted-foreground/70" />
              GitHub
            </Label>
            <Input
              id="github-in"
              placeholder="username or github.com/username"
              value={value.github}
              onChange={(e) => set('github', e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="linkedin-in">
              <Fingerprint className="size-3.5 text-muted-foreground/70" />
              LinkedIn
              <span className="font-normal text-muted-foreground/60">
                · verify only
              </span>
            </Label>
            <Input
              id="linkedin-in"
              placeholder="username to cross-check"
              value={value.linkedin}
              onChange={(e) => set('linkedin', e.target.value)}
            />
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 pt-1">
          <p className="flex items-center gap-1.5 text-[12px] text-muted-foreground/70">
            <Database className="size-3.5" />
            At least one source is required.
          </p>
          <Button onClick={onRun} disabled={running || !hasInput} size="lg">
            {running ? (
              <>
                <Loader2 className="animate-spin" /> Transforming…
              </>
            ) : (
              <>
                Run pipeline <ArrowRight />
              </>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
