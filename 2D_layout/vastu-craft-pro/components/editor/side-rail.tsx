import {
  PenLine,
  MousePointer2,
  DoorOpen,
  Armchair,
  Crosshair,
  Compass,
  Sparkles,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

const tabs: { id: string; label: string; icon: LucideIcon; active?: boolean }[] = [
  { id: 'draw', label: 'Draw', icon: PenLine, active: true },
  { id: 'edit', label: 'Edit', icon: MousePointer2 },
  { id: 'room', label: 'Room', icon: DoorOpen },
  { id: 'furniture', label: 'Furnish', icon: Armchair },
  { id: 'coords', label: 'Coords', icon: Crosshair },
  { id: 'vastu', label: 'Vastu', icon: Compass },
  { id: 'generate', label: 'Generate', icon: Sparkles },
]

export function SideRail() {
  return (
    <nav
      aria-label="Workspace tabs"
      className="flex w-16 shrink-0 flex-col items-center gap-1 border-r border-border bg-sidebar py-2"
    >
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          aria-current={tab.active ? 'page' : undefined}
          className={
            tab.active
              ? 'flex w-14 flex-col items-center gap-1 rounded-lg bg-primary/15 py-2 text-primary'
              : 'flex w-14 flex-col items-center gap-1 rounded-lg py-2 text-muted-foreground hover:bg-sidebar-accent hover:text-foreground'
          }
        >
          <tab.icon className="size-4.5" />
          <span className="text-[10px] font-medium leading-none">{tab.label}</span>
        </button>
      ))}
    </nav>
  )
}
