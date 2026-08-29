import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold tracking-wide uppercase',
  {
    variants: {
      variant: {
        default: 'border-[var(--color-border)] bg-[var(--color-surface-2)] text-[var(--color-fg-dim)]',
        accent: 'border-[var(--color-accent)]/30 bg-[var(--color-accent)]/15 text-[var(--color-accent)]',
        pass: 'border-[var(--color-pass)]/30 bg-[var(--color-pass)]/15 text-[var(--color-pass)]',
        fail: 'border-[var(--color-fail)]/30 bg-[var(--color-fail)]/15 text-[var(--color-fail)]',
        warn: 'border-[var(--color-warn)]/30 bg-[var(--color-warn)]/15 text-[var(--color-warn)]',
        none: 'border-[var(--color-none)]/30 bg-[var(--color-none)]/10 text-[var(--color-none)]',
      },
    },
    defaultVariants: { variant: 'default' },
  },
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />
}
