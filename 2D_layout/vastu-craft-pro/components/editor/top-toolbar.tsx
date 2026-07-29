import {
  Home,
  ChevronDown,
  Undo2,
  Redo2,
  Save,
  FolderOpen,
  Download,
  Wrench,
  Box,
  LayoutGrid,
  CircleHelp,
} from 'lucide-react'

function Divider() {
  return <div className="h-6 w-px bg-border" aria-hidden="true" />
}

export function TopToolbar() {
  return (
    <header className="flex h-12 shrink-0 items-center gap-2 border-b border-border bg-card px-3">
      {/* Brand */}
      <div className="flex items-center gap-2 pr-1">
        <div className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <Home className="size-4" />
        </div>
        <span className="text-sm font-semibold tracking-tight">
          VastuCraft <span className="text-primary">Pro</span>
        </span>
      </div>

      <Divider />

      {/* Project selector */}
      <button
        type="button"
        className="flex items-center gap-2 rounded-md px-2.5 py-1.5 text-sm text-foreground hover:bg-accent"
      >
        <span className="font-medium">Sunrise Villa — Ground Floor</span>
        <ChevronDown className="size-3.5 text-muted-foreground" />
      </button>

      <Divider />

      {/* History */}
      <div className="flex items-center gap-1">
        <button
          type="button"
          aria-label="Undo"
          className="flex size-8 items-center justify-center rounded-md text-foreground hover:bg-accent"
        >
          <Undo2 className="size-4" />
        </button>
        <button
          type="button"
          aria-label="Redo"
          className="flex size-8 items-center justify-center rounded-md text-muted-foreground/50"
          disabled
        >
          <Redo2 className="size-4" />
        </button>
      </div>

      <Divider />

      {/* File actions */}
      <div className="flex items-center gap-1">
        <button
          type="button"
          className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm text-foreground hover:bg-accent"
        >
          <Save className="size-4" />
          Save
        </button>
        <button
          type="button"
          className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm text-foreground hover:bg-accent"
        >
          <FolderOpen className="size-4" />
          Load
        </button>
        <button
          type="button"
          className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm text-foreground hover:bg-accent"
        >
          <Download className="size-4" />
          Export
          <ChevronDown className="size-3 text-muted-foreground" />
        </button>
        <button
          type="button"
          className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm text-foreground hover:bg-accent"
        >
          <Wrench className="size-4" />
          Tools
          <ChevronDown className="size-3 text-muted-foreground" />
        </button>
      </div>

      <div className="flex-1" />

      {/* Units */}
      <div className="flex items-center rounded-md border border-border p-0.5 text-xs font-medium">
        <button type="button" className="rounded bg-secondary px-2 py-1 text-foreground">
          ft
        </button>
        <button type="button" className="px-2 py-1 text-muted-foreground hover:text-foreground">
          m
        </button>
        <button type="button" className="px-2 py-1 text-muted-foreground hover:text-foreground">
          cm
        </button>
      </div>

      {/* 2D / 3D mode toggle */}
      <div className="flex items-center rounded-md border border-border p-0.5 text-xs font-medium">
        <button
          type="button"
          className="flex items-center gap-1.5 rounded bg-primary px-2.5 py-1 text-primary-foreground"
        >
          <LayoutGrid className="size-3.5" />
          Plan
        </button>
        <button
          type="button"
          className="flex items-center gap-1.5 px-2.5 py-1 text-muted-foreground hover:text-foreground"
        >
          <Box className="size-3.5" />
          3D View
        </button>
      </div>

      <button
        type="button"
        aria-label="Help guide"
        className="flex size-8 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
      >
        <CircleHelp className="size-4" />
      </button>
    </header>
  )
}
