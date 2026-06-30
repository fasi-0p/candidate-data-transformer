import { motion } from 'framer-motion'
import {
  Braces,
  Briefcase,
  GitBranch,
  GraduationCap,
  Link2,
  Mail,
  MapPin,
  Phone,
  Sparkles,
  User,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { ConfidenceBar } from './ConfidenceBar'
import { FieldGroup } from './FieldGroup'
import { SkillsRow } from './SkillsRow'
import { formatEducation, formatLink, formatLocation } from '@/lib/format'
import type { Candidate, Issue, ValidationReport } from '@/lib/types'

function initials(name: string | undefined): string {
  if (!name) return '?'
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? '')
    .join('')
}

function StatusBadges({ report }: { report?: ValidationReport }) {
  if (!report) return null
  const issues: Issue[] = report.issues ?? []
  const mismatch = (code: string) => issues.find((i) => i.code === code)
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {!report.is_valid && <Badge variant="destructive">invalid</Badge>}
      {mismatch('github_mismatch') && (
        <Badge variant="warning" title={mismatch('github_mismatch')!.message}>
          GitHub ✗
        </Badge>
      )}
      {mismatch('linkedin_mismatch') && (
        <Badge variant="warning" title={mismatch('linkedin_mismatch')!.message}>
          LinkedIn ✗
        </Badge>
      )}
    </div>
  )
}

export function CandidateCard({
  candidate: c,
  report,
  index,
}: {
  candidate: Candidate
  report?: ValidationReport
  index: number
}) {
  const name = c.full_name?.value
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.06, ease: [0.22, 1, 0.36, 1] }}
    >
      <Card className="overflow-hidden">
        {/* header */}
        <div className="flex items-start gap-4 border-b border-border/60 bg-gradient-to-b from-secondary/40 to-transparent p-5">
          <div className="flex size-11 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
            {initials(name)}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h3 className="truncate text-[17px] font-semibold tracking-[-0.01em]">
                {name ?? 'Unknown candidate'}
              </h3>
              <StatusBadges report={report} />
            </div>
            <p className="mt-0.5 truncate text-[13px] text-muted-foreground">
              {c.headline?.value ?? c.candidate_id}
            </p>
          </div>
          <div className="hidden shrink-0 flex-col items-end gap-1 sm:flex">
            <span className="flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground/70">
              <Sparkles className="size-3" /> confidence
            </span>
            <ConfidenceBar value={c.record_confidence} />
          </div>
        </div>

        {/* fields */}
        <div className="divide-y divide-border/40 py-1.5">
          <FieldGroup label="Headline" icon={Braces} items={c.headline ? [c.headline] : []} />
          <FieldGroup
            label="Location"
            icon={MapPin}
            items={c.location ? [c.location] : []}
            fmt={formatLocation}
          />
          <FieldGroup
            label="Experience"
            icon={Briefcase}
            items={c.years_experience ? [c.years_experience] : []}
            fmt={(v) => `${v} yrs`}
          />
          <FieldGroup label="Emails" icon={Mail} items={c.emails} />
          <FieldGroup label="Phones" icon={Phone} items={c.phones} />
          <SkillsRow label="Skills" icon={User} items={c.skills} />
          <FieldGroup label="Links" icon={Link2} items={c.links} fmt={formatLink} />
          <FieldGroup
            label="Education"
            icon={GraduationCap}
            items={c.education}
            fmt={formatEducation}
          />
        </div>

        <div className="flex items-center gap-1.5 border-t border-border/60 px-5 py-2.5 text-[11px] text-muted-foreground/60">
          <GitBranch className="size-3" />
          <span className="font-mono">{c.candidate_id}</span>
        </div>
      </Card>
    </motion.div>
  )
}
