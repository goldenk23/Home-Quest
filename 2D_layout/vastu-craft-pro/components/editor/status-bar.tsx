import { Magnet, Grid3x3, MousePointer2 } from 'lucide-react'

export function StatusBar() {
  return (
    <footer className="flex h-8 shrink-0 items-center gap-4 border-t border-border bg-card px-3 font-mono text-[11px] text-muted-foreground">
      <span className="flex items-center gap-1.5">
        <MousePointer2 className="size-3" />
        x: 18&apos; 4&quot; &nbsp; y: 9&apos; 2&quot;
      </span>
      <span className="hidden sm:inline">Zoom 100%</span>
      <span className="flex items-center gap-1 text-primary">
        <Magnet className="size-3" /> Snap
      </span>
      <span className="flex items-center gap-1 text-primary">
        <Grid3x3 className="size-3" /> Grid 1 ft
      </span>
      <div className="flex-1" />
      <span className="hidden md:inline">5 rooms · 1 selected</span>
      <span className="flex items-center gap-1.5">
        <span className="size-1.5 rounded-full bg-primary" aria-hidden="true" />
        Saved
      </span>
    </footer>
  )
}
