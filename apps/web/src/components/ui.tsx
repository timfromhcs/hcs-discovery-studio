import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import { createPortal } from "react-dom";
import { NavLink } from "react-router-dom";
import type { NodeStatus, RunStatus } from "../api/types";
import { Icon, type IconName } from "./Icon";

/* ------------------------------------------------------------------ buttons */
type Variant = "primary" | "secondary" | "ghost" | "danger" | "quiet";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  icon?: IconName;
  iconRight?: IconName;
  loading?: boolean;
}

export function Button({
  variant = "secondary",
  size = "md",
  icon,
  iconRight,
  loading = false,
  className = "",
  children,
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <button
      className={`btn btn-${variant} btn-${size} ${className}`.trim()}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? <span className="spinner" aria-hidden="true" /> : icon ? <Icon name={icon} size={size === "sm" ? 15 : 17} /> : null}
      {children ? <span>{children}</span> : null}
      {iconRight ? <Icon name={iconRight} size={size === "sm" ? 15 : 17} /> : null}
    </button>
  );
}

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon: IconName;
  label: string;
  size?: number;
}

export function IconButton({ icon, label, size = 18, className = "", ...rest }: IconButtonProps) {
  return (
    <button className={`icon-btn ${className}`.trim()} aria-label={label} title={label} {...rest}>
      <Icon name={icon} size={size} />
    </button>
  );
}

export function LinkButton({
  to,
  icon,
  children,
  variant = "secondary",
  size = "md",
}: {
  to: string;
  icon?: IconName;
  children: ReactNode;
  variant?: Variant;
  size?: Size;
}) {
  return (
    <NavLink to={to} className={`btn btn-${variant} btn-${size}`}>
      {icon ? <Icon name={icon} size={size === "sm" ? 15 : 17} /> : null}
      <span>{children}</span>
    </NavLink>
  );
}

/* ------------------------------------------------------------------ surfaces */
export function Card({
  children,
  className = "",
  as: Tag = "section",
}: {
  children: ReactNode;
  className?: string;
  as?: "section" | "article" | "div";
}) {
  return <Tag className={`card ${className}`.trim()}>{children}</Tag>;
}

export function CardHeader({
  title,
  subtitle,
  actions,
  icon,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  icon?: IconName;
}) {
  return (
    <header className="card-header">
      <div className="card-header-main">
        {icon ? (
          <span className="card-header-icon">
            <Icon name={icon} size={18} />
          </span>
        ) : null}
        <div>
          <h2>{title}</h2>
          {subtitle ? <p className="muted small">{subtitle}</p> : null}
        </div>
      </div>
      {actions ? <div className="card-actions">{actions}</div> : null}
    </header>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  meta,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  meta?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div className="page-header-text">
        {eyebrow ? <div className="eyebrow">{eyebrow}</div> : null}
        <h1>{title}</h1>
        {description ? <p className="page-description">{description}</p> : null}
        {meta ? <div className="page-meta">{meta}</div> : null}
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </header>
  );
}

export function Stat({
  label,
  value,
  hint,
  icon,
  to,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  icon?: IconName;
  to?: string;
}) {
  const content = (
    <>
      <div className="stat-top">
        <span>{label}</span>
        {icon ? <Icon name={icon} size={16} /> : null}
      </div>
      <div className="stat-value tabular">{value}</div>
      {hint ? <div className="stat-hint">{hint}</div> : null}
    </>
  );
  return to ? (
    <NavLink to={to} className="stat-card stat-link">
      {content}
    </NavLink>
  ) : (
    <div className="stat-card">{content}</div>
  );
}

/* ------------------------------------------------------------------ badges */
export function Badge({
  children,
  tone = "neutral",
  dot = false,
  title,
}: {
  children: ReactNode;
  tone?: "neutral" | "accent" | "ok" | "warn" | "danger" | "info" | "muted";
  dot?: boolean;
  title?: string;
}) {
  return (
    <span className={`badge badge-${tone}`} title={title}>
      {dot ? <span className="badge-dot" aria-hidden="true" /> : null}
      {children}
    </span>
  );
}

export function runTone(status: RunStatus): "ok" | "warn" | "danger" | "info" | "muted" {
  if (status === "succeeded") return "ok";
  if (status === "failed") return "danger";
  if (status === "cancelled") return "muted";
  if (status === "running") return "info";
  return "warn";
}

export function RunStatusBadge({ status }: { status: RunStatus }) {
  const label = status === "queued" ? "Queued" : status === "running" ? "Running" : status === "succeeded" ? "Succeeded" : status === "failed" ? "Failed" : "Cancelled";
  return (
    <Badge tone={runTone(status)} dot>
      {label}
    </Badge>
  );
}

export function NodeStatusBadge({ status, cached }: { status: NodeStatus; cached?: boolean }) {
  const tone = status === "succeeded" ? "ok" : status === "failed" ? "danger" : status === "running" ? "info" : status === "cancelled" ? "muted" : "warn";
  return (
    <span className="inline-badges">
      <Badge tone={tone} dot>
        {status}
      </Badge>
      {cached ? <Badge tone="accent">cached</Badge> : null}
    </span>
  );
}

export function ModelStatusBadge({ status }: { status: string }) {
  const tone =
    status === "available"
      ? "ok"
      : status === "available_with_limits"
        ? "warn"
        : status === "planned"
          ? "muted"
          : status === "unavailable"
            ? "danger"
            : "info";
  return <Badge tone={tone}>{status.replaceAll("_", " ")}</Badge>;
}

/* ------------------------------------------------------------------ states */
export function EmptyState({
  icon = "flask",
  title,
  description,
  actions,
  compact = false,
}: {
  icon?: IconName;
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  compact?: boolean;
}) {
  return (
    <div className={`empty-state ${compact ? "compact" : ""}`.trim()}>
      <span className="empty-icon">
        <Icon name={icon} size={compact ? 20 : 26} />
      </span>
      <h3>{title}</h3>
      {description ? <p>{description}</p> : null}
      {actions ? <div className="empty-actions">{actions}</div> : null}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : "Something went wrong.";
  const code = error && typeof error === "object" && "code" in error ? String(error.code) : null;
  return (
    <div className="error-state" role="alert">
      <span className="empty-icon error">
        <Icon name="alert" size={22} />
      </span>
      <div>
        <h3>Could not load this view</h3>
        <p>{message}</p>
        {code ? <code className="small">{code}</code> : null}
      </div>
      {onRetry ? (
        <Button size="sm" icon="refresh" onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`.trim()} aria-hidden="true" />;
}

export function LoadingBlock({ rows = 4 }: { rows?: number }) {
  return (
    <div className="loading-block" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton key={index} className={index === 0 ? "skeleton-title" : "skeleton-row"} />
      ))}
    </div>
  );
}

export function InlineNotice({
  tone = "info",
  title,
  children,
  icon,
}: {
  tone?: "info" | "warn" | "danger" | "ok";
  title?: ReactNode;
  children?: ReactNode;
  icon?: IconName;
}) {
  return (
    <div className={`notice notice-${tone}`} role={tone === "danger" ? "alert" : "note"}>
      <Icon name={icon ?? (tone === "danger" ? "alert" : tone === "warn" ? "alert" : "info")} size={18} />
      <div>
        {title ? <strong>{title}</strong> : null}
        {children ? <div className="notice-body">{children}</div> : null}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ forms */
export function Field({
  label,
  hint,
  error,
  children,
  htmlFor,
  required,
}: {
  label: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  children: ReactNode;
  htmlFor?: string;
  required?: boolean;
}) {
  return (
    <div className="field">
      <label htmlFor={htmlFor}>
        {label}
        {required ? <span className="required" aria-hidden="true"> *</span> : null}
      </label>
      {children}
      {hint ? <p className="field-hint">{hint}</p> : null}
      {error ? <p className="field-error">{error}</p> : null}
    </div>
  );
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`input ${props.className ?? ""}`.trim()} {...props} />;
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={`input select ${props.className ?? ""}`.trim()} {...props} />;
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={`input textarea ${props.className ?? ""}`.trim()} {...props} />;
}

export function Checkbox({
  label,
  description,
  ...rest
}: InputHTMLAttributes<HTMLInputElement> & { label: ReactNode; description?: ReactNode }) {
  return (
    <label className="checkbox">
      <input type="checkbox" {...rest} />
      <span>
        <span className="checkbox-label">{label}</span>
        {description ? <span className="checkbox-description">{description}</span> : null}
      </span>
    </label>
  );
}

/* ------------------------------------------------------------------ modal */
export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  width = "md",
  tone = "default",
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  width?: "sm" | "md" | "lg" | "xl";
  tone?: "default" | "danger";
}) {
  const titleId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    previousFocus.current = document.activeElement as HTMLElement | null;
    const timer = window.setTimeout(() => {
      const focusable = panelRef.current?.querySelector<HTMLElement>(
        "input, select, textarea, button:not([disabled]), [href], [tabindex]:not([tabindex='-1'])",
      );
      focusable?.focus();
    }, 20);
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key !== "Tab" || !panelRef.current) return;
      const nodes = Array.from(
        panelRef.current.querySelectorAll<HTMLElement>(
          "input:not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled]), [href], [tabindex]:not([tabindex='-1'])",
        ),
      ).filter((node) => node.offsetParent !== null);
      if (!nodes.length) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
      window.clearTimeout(timer);
      previousFocus.current?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div
        ref={panelRef}
        className={`modal modal-${width} ${tone === "danger" ? "modal-danger" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <header className="modal-header">
          <div>
            <h2 id={titleId}>{title}</h2>
            {description ? <p className="muted small">{description}</p> : null}
          </div>
          <IconButton icon="close" label="Close dialog" onClick={onClose} />
        </header>
        <div className="modal-body">{children}</div>
        {footer ? <footer className="modal-footer">{footer}</footer> : null}
      </div>
    </div>,
    document.body,
  );
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  confirmVariant = "danger",
  onConfirm,
  onClose,
  busy = false,
  children,
}: {
  open: boolean;
  title: string;
  description?: ReactNode;
  confirmLabel?: string;
  confirmVariant?: Variant;
  onConfirm: () => void;
  onClose: () => void;
  busy?: boolean;
  children?: ReactNode;
}) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      description={description}
      width="sm"
      tone={confirmVariant === "danger" ? "danger" : "default"}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button variant={confirmVariant} onClick={onConfirm} loading={busy}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      {children}
    </Modal>
  );
}

/* ------------------------------------------------------------------ toast */
interface Toast {
  id: number;
  message: string;
  tone: "ok" | "danger" | "info";
}

interface ToastContextValue {
  notify: (message: string, tone?: Toast["tone"]) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const counter = useRef(0);

  const notify = useCallback((message: string, tone: Toast["tone"] = "info") => {
    counter.current += 1;
    const id = counter.current;
    setToasts((current) => [...current.slice(-3), { id, message, tone }]);
    window.setTimeout(() => setToasts((current) => current.filter((toast) => toast.id !== id)), 5000);
  }, []);

  const value = useMemo(() => ({ notify }), [notify]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-stack" aria-live="polite" aria-atomic="false">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast toast-${toast.tone}`}>
            <Icon name={toast.tone === "ok" ? "check" : toast.tone === "danger" ? "alert" : "info"} size={16} />
            <span>{toast.message}</span>
            <button
              className="toast-close"
              aria-label="Dismiss notification"
              onClick={() => setToasts((current) => current.filter((item) => item.id !== toast.id))}
            >
              <Icon name="close" size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used inside ToastProvider");
  return context;
}

/* ------------------------------------------------------------------ misc */
export function CopyButton({ value, label = "Copy", compact = false }: { value: string; label?: string; compact?: boolean }) {
  const { notify } = useToast();
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      notify("Copied to clipboard", "ok");
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      notify("Clipboard access was denied", "danger");
    }
  };
  if (compact) {
    return (
      <button className="copy-inline" onClick={copy} aria-label={copied ? "Copied" : label} title={label}>
        <Icon name={copied ? "check" : "copy"} size={14} />
      </button>
    );
  }
  return (
    <Button size="sm" variant="quiet" icon={copied ? "check" : "copy"} onClick={copy}>
      {copied ? "Copied" : label}
    </Button>
  );
}

export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
  label,
}: {
  tabs: Array<{ id: T; label: string; count?: number }>;
  value: T;
  onChange: (value: T) => void;
  label: string;
}) {
  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {tabs.map((tab) => (
        <button
          key={tab.id}
          role="tab"
          aria-selected={tab.id === value}
          className={tab.id === value ? "tab active" : "tab"}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
          {tab.count !== undefined ? <span className="tab-count">{tab.count}</span> : null}
        </button>
      ))}
    </div>
  );
}

export function KeyValue({ items }: { items: Array<{ label: ReactNode; value: ReactNode; mono?: boolean }> }) {
  return (
    <dl className="key-value">
      {items.map((item, index) => (
        <div key={index}>
          <dt>{item.label}</dt>
          <dd className={item.mono ? "mono" : ""}>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function ProgressBar({ value, label }: { value: number | null; label?: string }) {
  const pct = value === null ? null : Math.round(Math.min(1, Math.max(0, value)) * 100);
  return (
    <div className="progress" aria-label={label ?? "Progress"}>
      <div className={`progress-bar ${pct === null ? "indeterminate" : ""}`} style={pct === null ? undefined : { width: `${pct}%` }} />
      <span className="progress-text">{pct === null ? "no estimate" : `${pct}%`}</span>
    </div>
  );
}
