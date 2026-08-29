import * as React from 'react'
import { cn } from '@/lib/utils'

interface SwitchProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'onChange'> {
  checked: boolean
  onCheckedChange: (next: boolean) => void
  label?: string
}

export function Switch({ checked, onCheckedChange, label, className, id, ...props }: SwitchProps) {
  return (
    <button
      id={id}
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border transition-colors',
        checked
          ? 'bg-[var(--color-accent)] border-[var(--color-accent)]'
          : 'bg-[var(--color-surface-2)] border-[var(--color-border)]',
        className,
      )}
      {...props}
    >
      <span
        className={cn(
          'pointer-events-none absolute top-0.5 left-0.5 h-3.5 w-3.5 rounded-full bg-white transition-transform',
          checked && 'translate-x-4',
        )}
      />
    </button>
  )
}
