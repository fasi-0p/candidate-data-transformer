import type { ComponentProps } from 'react'
import { cn } from '@/lib/utils'

function Input({ className, type, ...props }: ComponentProps<'input'>) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        'flex h-10 w-full rounded-xl border border-input bg-card px-3.5 py-2 text-sm shadow-xs transition-[color,box-shadow,border-color] outline-none',
        'placeholder:text-muted-foreground/70',
        'focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/25',
        'disabled:cursor-not-allowed disabled:opacity-50',
        'file:mr-3 file:rounded-lg file:border-0 file:bg-secondary file:px-3 file:py-1.5 file:text-[13px] file:font-medium file:text-secondary-foreground hover:file:bg-accent file:cursor-pointer file:transition-colors',
        className,
      )}
      {...props}
    />
  )
}

export { Input }
