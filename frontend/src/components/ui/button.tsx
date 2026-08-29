import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 rounded-md text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]',
  {
    variants: {
      variant: {
        default: 'bg-[var(--color-accent)] text-white hover:brightness-110',
        secondary:
          'bg-[var(--color-surface-2)] text-[var(--color-fg)] border border-[var(--color-border)] hover:border-[var(--color-border-strong)]',
        ghost: 'hover:bg-[var(--color-surface-2)] text-[var(--color-fg-dim)]',
        danger: 'bg-[var(--color-fail)]/15 text-[var(--color-fail)] border border-[var(--color-fail)]/30 hover:bg-[var(--color-fail)]/25',
        success:
          'bg-[var(--color-pass)]/15 text-[var(--color-pass)] border border-[var(--color-pass)]/30 hover:bg-[var(--color-pass)]/25',
      },
      size: {
        default: 'h-9 px-3.5',
        sm: 'h-8 px-2.5 text-xs',
        lg: 'h-10 px-4',
        icon: 'h-9 w-9',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
  ),
)
Button.displayName = 'Button'
