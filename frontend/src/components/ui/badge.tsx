import { cva, type VariantProps } from 'class-variance-authority'
import type { ComponentProps } from 'react'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-medium tracking-wide transition-colors [&_svg]:size-3',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-secondary text-secondary-foreground',
        primary:
          'border-transparent bg-primary/10 text-primary',
        success:
          'border-transparent bg-[color-mix(in_oklch,var(--color-success)_14%,transparent)] text-[var(--color-success)]',
        warning:
          'border-transparent bg-[color-mix(in_oklch,var(--color-warning)_16%,transparent)] text-[oklch(0.52_0.14_70)]',
        destructive:
          'border-transparent bg-destructive/10 text-destructive',
        outline: 'border-border text-muted-foreground',
      },
    },
    defaultVariants: { variant: 'default' },
  },
)

function Badge({
  className,
  variant,
  ...props
}: ComponentProps<'span'> & VariantProps<typeof badgeVariants>) {
  return (
    <span
      data-slot="badge"
      className={cn(badgeVariants({ variant }), className)}
      {...props}
    />
  )
}

export { Badge, badgeVariants }
