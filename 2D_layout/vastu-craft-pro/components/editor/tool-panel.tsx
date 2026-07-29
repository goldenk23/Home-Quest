import {
  Slash,
  Spline,
  Square,
  Shapes,
  Magnet,
  Grid3x3,
  Eraser,
  ZoomIn,
  ZoomOut,
  Maximize,
  ChevronDown,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h3 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </h3>
      {children}
    </section>
  )
}

function ToolButton({
  icon: Icon,
  label,
  active,
  disabled,
}: {
  icon: LucideIcon
  label: string
  active?: boolean
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      aria-pressed={active}
      className={
        active
          ? 'flex flex-col items-center gap-1.5 rounded-lg border border-primary/50 bg-primary/15 px-1 py-2.5 text-primary'
          : disabled
            ? 'flex flex-col items-center gap-1.5 rounded-lg border border-border/50 px-1 py-2.5 text-muted-foreground/40'
            : 'flex flex-col items-center gap-1.5 rounded-lg border border-border px-1 py-2.5 text-foreground hover:border-primary/40 hover:bg-accent'
      }
    >
      <Icon className="size-4" />
      <span className="text-[10px] font-medium leading-none">{label}</span>
    </button>
  )
}

function ToggleRow({
  icon: Icon,
  label,
  on,
}: {
  icon: LucideIcon
  label: string
  on?: boolean
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      className="flex items-center justify-between rounded-lg border border-border px-3 py-2 hover:bg-accent"
    >
      <span className="flex items-center gap-2 text-sm text-foreground">
        <Icon className="size-4 text-muted-foreground" />
        {label}
      </span>
      <span
        className={
          on
            ? 'flex h-4.5 w-8 items-center rounded-full bg-primary px-0.5'
            : 'flex h-4.5 w-8 items-center rounded-full bg-secondary px-0.5'
        }
      >
        <span
          className={
            on
              ? 'ml-auto size-3.5 rounded-full bg-primary-foreground'
              : 'size-3.5 rounded-full bg-muted-foreground'
          }
        />
      </span>
    </button>
  )
}

export function ToolPanel() {
  return (
    <aside className="flex w-56 shrink-0 flex-col gap-5 overflow-y-auto border-r border-border bg-card p-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">Draw</h2>
        <span className="rounded-full bg-primary/15 px-2 py-0.5 text-[10px] font-medium text-primary">
          Wall tool active
        </span>
      </div>

      <Section title="Drawing">
        <div className="grid grid-cols-2 gap-1.5">
          <ToolButton icon={Slash} label="Wall" active />
          <ToolButton icon={Spline} label="Polyline" />
          <ToolButton icon={Square} label="Rectangle" />
          <ToolButton icon={Shapes} label="Lines to Room" />
        </div>
      </Section>

      <Section title="Snapping & Grid">
        <div className="flex flex-col gap-1.5">
          <ToggleRow icon={Magnet} label="Snap to grid" on />
          <ToggleRow icon={Grid3x3} label="Show grid" on />
        </div>
        <div className="flex items-center justify-between rounded-lg border border-border px-3 py-2">
          <span className="text-sm text-foreground">Grid spacing</span>
          <button type="button" className="flex items-center gap-1 text-sm font-medium text-primary">
            1 ft <ChevronDown className="size-3" />
          </button>
        </div>
      </Section>

      <Section title="Erase">
        <div className="grid grid-cols-2 gap-1.5">
          <ToolButton icon={Eraser} label="Erase Wall" disabled />
          <ToolButton icon={Eraser} label="Erase All" disabled />
        </div>
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          Available when a walls-only room exists.
        </p>
      </Section>

      <Section title="Zoom">
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            aria-label="Zoom out"
            className="flex h-8 flex-1 items-center justify-center rounded-lg border border-border text-foreground hover:bg-accent"
          >
            <ZoomOut className="size-4" />
          </button>
          <span className="min-w-12 text-center font-mono text-xs text-foreground">100%</span>
          <button
            type="button"
            aria-label="Zoom in"
            className="flex h-8 flex-1 items-center justify-center rounded-lg border border-border text-foreground hover:bg-accent"
          >
            <ZoomIn className="size-4" />
          </button>
          <button
            type="button"
            aria-label="Fit to view"
            className="flex h-8 flex-1 items-center justify-center rounded-lg border border-border text-foreground hover:bg-accent"
          >
            <Maximize className="size-4" />
          </button>
        </div>
      </Section>
    </aside>
  )
}
