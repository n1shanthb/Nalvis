import type { ReactNode } from "react";
import { Link } from "react-router-dom";

export function PageHead({ eyebrow, title, subtitle, action }: { eyebrow?: string; title: string; subtitle?: ReactNode; action?: ReactNode }) {
  return (
    <header className="page-header">
      <div className="page-header-main">
        {eyebrow && <p className="page-kicker">{eyebrow}</p>}
        <h1 className="page-title">{title}</h1>
        {subtitle && <p className="page-lead">{subtitle}</p>}
      </div>
      {action && <div className="page-actions">{action}</div>}
    </header>
  );
}

export function StatRow({ items }: { items: Array<[string | number, string]> }) {
  return (
    <section className="kpi-row" aria-label="Summary">
      {items.map(([value, label]) => (
        <div className="kpi" key={label}>
          <span className="kpi-value">{value}</span>
          <span className="kpi-label">{label}</span>
        </div>
      ))}
    </section>
  );
}

export function Panel({ title, hint, children, action }: { title: string; hint?: string; children: ReactNode; action?: ReactNode }) {
  return (
    <section className="surface">
      <div className="surface-header">
        <h2 className="surface-title">{title}</h2>
        {hint && <span className="surface-hint">{hint}</span>}
        {action}
      </div>
      {children}
    </section>
  );
}

export function Chip({ children, soft = false, tone = "" }: { children: ReactNode; soft?: boolean; tone?: "" | "good" | "bad" | "accent" | "warning" }) {
  const cls = ["tag", soft && "muted", tone === "good" && "success", tone === "bad" && "danger", tone === "accent" && "accent", tone === "warning" && "warning"].filter(Boolean).join(" ");
  return <span className={cls}>{children}</span>;
}

export const Badge = Chip;

export function PlainList<T>({ rows, render }: { rows: T[]; render: (item: T) => ReactNode }) {
  return (
    <ul className="list-plain">
      {rows.map((item, index) => (
        <li key={index}>{render(item)}</li>
      ))}
    </ul>
  );
}

export function Btn({ children, className = "", type = "button", ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { children: ReactNode }) {
  return (
    <button type={type} className={`btn ${className}`.trim()} {...props}>
      {children}
    </button>
  );
}

export function BtnLink({ to, children, className = "", onClick }: { to: string; children: ReactNode; className?: string; onClick?: () => void }) {
  return (
    <Link className={`btn ${className}`.trim()} to={to} onClick={onClick}>
      {children}
    </Link>
  );
}

export function Loading({ text = "Loading…" }: { text?: string }) {
  return <div className="state">{text}</div>;
}

export function ErrorState({ error }: { error: Error }) {
  return <div className="state error">{error.message}</div>;
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <p className="empty">
      <strong>{title}</strong>
      {description ? ` — ${description}` : ""}
    </p>
  );
}

export function ProjectList<T>({ rows, link, render }: { rows: T[]; link: (item: T) => string; render: (item: T) => ReactNode }) {
  return (
    <ul className="list-rows">
      {rows.map((item, index) => (
        <li key={index}>
          <Link to={link(item)}>{render(item)}</Link>
        </li>
      ))}
    </ul>
  );
}

export const PageHeader = PageHead;
export const Card = Panel;

export function List<T>({ rows, render, link, itemKey }: { rows: T[]; render: (item: T) => ReactNode; link?: (item: T) => string; itemKey?: (item: T, index: number) => string | number }) {
  if (!link) return <PlainList rows={rows} render={render} />;
  return (
    <ul className="list-rows">
      {rows.map((item, index) => (
        <li key={itemKey?.(item, index) ?? index}>
          <Link to={link(item)}>{render(item)}</Link>
        </li>
      ))}
    </ul>
  );
}
