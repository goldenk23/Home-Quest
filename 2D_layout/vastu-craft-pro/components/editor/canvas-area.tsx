import { Compass, Plus, Minus, Locate } from 'lucide-react'

function FloorPlan() {
  return (
    <svg
      viewBox="0 0 640 480"
      className="h-full w-full"
      role="img"
      aria-label="Floor plan of Sunrise Villa ground floor"
    >
      <defs>
        <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">
          <path
            d="M 24 0 L 0 0 0 24"
            fill="none"
            className="stroke-canvas-grid"
            strokeWidth="1"
          />
        </pattern>
      </defs>

      {/* Grid */}
      <rect width="640" height="480" fill="url(#grid)" />

      {/* Outer walls */}
      <rect
        x="96"
        y="72"
        width="432"
        height="336"
        fill="none"
        className="stroke-canvas-ink"
        strokeWidth="6"
      />

      {/* Interior walls */}
      <line x1="312" y1="72" x2="312" y2="264" className="stroke-canvas-ink" strokeWidth="4" />
      <line x1="96" y1="264" x2="432" y2="264" className="stroke-canvas-ink" strokeWidth="4" />
      <line x1="432" y1="264" x2="432" y2="408" className="stroke-canvas-ink" strokeWidth="4" />
      <line x1="432" y1="168" x2="528" y2="168" className="stroke-canvas-ink" strokeWidth="4" />

      {/* Door swings */}
      <path d="M 312 150 A 36 36 0 0 1 348 186" fill="none" stroke="oklch(0.55 0.02 250)" strokeWidth="1.5" strokeDasharray="3 3" />
      <line x1="312" y1="150" x2="312" y2="186" stroke="oklch(0.97 0 90)" strokeWidth="5" />
      <path d="M 240 264 A 34 34 0 0 1 206 298" fill="none" stroke="oklch(0.55 0.02 250)" strokeWidth="1.5" strokeDasharray="3 3" />
      <line x1="240" y1="264" x2="206 " y2="264" stroke="oklch(0.97 0 90)" strokeWidth="5" />

      {/* Windows */}
      <line x1="150" y1="72" x2="230" y2="72" stroke="oklch(0.78 0.13 185)" strokeWidth="6" />
      <line x1="370" y1="408" x2="440" y2="408" stroke="oklch(0.78 0.13 185)" strokeWidth="6" />
      <line x1="528" y1="220" x2="528" y2="300" stroke="oklch(0.78 0.13 185)" strokeWidth="6" />

      {/* Selected room highlight — Living Room */}
      <rect
        x="99"
        y="75"
        width="210"
        height="186"
        fill="oklch(0.78 0.13 185 / 0.12)"
        stroke="oklch(0.78 0.13 185)"
        strokeWidth="1.5"
        strokeDasharray="6 4"
      />
      {/* Selection handles */}
      {[
        [99, 75],
        [309, 75],
        [99, 261],
        [309, 261],
      ].map(([x, y]) => (
        <rect
          key={`${x}-${y}`}
          x={x - 4}
          y={y - 4}
          width="8"
          height="8"
          fill="oklch(0.78 0.13 185)"
          stroke="white"
          strokeWidth="1.5"
        />
      ))}

      {/* Room labels */}
      <g className="fill-canvas-ink" fontSize="13" fontWeight="600" textAnchor="middle">
        <text x="204" y="160">Living Room</text>
        <text x="420" y="160">Kitchen</text>
        <text x="264" y="336">Master Bedroom</text>
        <text x="480" y="336">Bath</text>
        <text x="480" y="120">Pooja</text>
      </g>
      <g fill="oklch(0.55 0.02 250)" fontSize="10" fontFamily="monospace" textAnchor="middle">
        <text x="204" y="178">14&apos; x 12&apos;6&quot;</text>
        <text x="420" y="178">10&apos; x 8&apos;</text>
        <text x="264" y="354">16&apos; x 11&apos;</text>
        <text x="480" y="354">6&apos; x 8&apos;</text>
      </g>

      {/* Dimension line (top) */}
      <g stroke="oklch(0.55 0.02 250)" strokeWidth="1">
        <line x1="96" y1="48" x2="528" y2="48" />
        <line x1="96" y1="42" x2="96" y2="54" />
        <line x1="528" y1="42" x2="528" y2="54" />
      </g>
      <text x="312" y="40" fill="oklch(0.45 0.02 250)" fontSize="10" fontFamily="monospace" textAnchor="middle">
        36&apos; 0&quot;
      </text>

      {/* Dimension line (left) */}
      <g stroke="oklch(0.55 0.02 250)" strokeWidth="1">
        <line x1="66" y1="72" x2="66" y2="408" />
        <line x1="60" y1="72" x2="72" y2="72" />
        <line x1="60" y1="408" x2="72" y2="408" />
      </g>
      <text
        x="56"
        y="240"
        fill="oklch(0.45 0.02 250)"
        fontSize="10"
        fontFamily="monospace"
        textAnchor="middle"
        transform="rotate(-90 56 240)"
      >
        28&apos; 0&quot;
      </text>
    </svg>
  )
}

export function CanvasArea() {
  return (
    <div className="relative flex-1 overflow-hidden bg-canvas">
      <FloorPlan />

      {/* North compass badge */}
      <div className="absolute right-4 top-4 flex flex-col items-center gap-1 rounded-xl border border-border bg-card/95 px-3 py-2 shadow-lg backdrop-blur">
        <Compass className="size-6 text-warning" />
        <span className="text-[10px] font-semibold tracking-wider text-muted-foreground">
          N 0°
        </span>
      </div>

      {/* Floating zoom controls */}
      <div className="absolute bottom-4 right-4 flex flex-col overflow-hidden rounded-lg border border-border bg-card shadow-lg">
        <button
          type="button"
          aria-label="Zoom in"
          className="flex size-9 items-center justify-center text-foreground hover:bg-accent"
        >
          <Plus className="size-4" />
        </button>
        <div className="h-px bg-border" />
        <button
          type="button"
          aria-label="Zoom out"
          className="flex size-9 items-center justify-center text-foreground hover:bg-accent"
        >
          <Minus className="size-4" />
        </button>
        <div className="h-px bg-border" />
        <button
          type="button"
          aria-label="Center view"
          className="flex size-9 items-center justify-center text-foreground hover:bg-accent"
        >
          <Locate className="size-4" />
        </button>
      </div>

      {/* Selection context pill */}
      <div className="absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-3 rounded-full border border-border bg-card/95 px-4 py-2 shadow-lg backdrop-blur">
        <span className="size-2 rounded-full bg-primary" aria-hidden="true" />
        <span className="text-xs font-medium text-foreground">Living Room selected</span>
        <span className="font-mono text-[11px] text-muted-foreground">14&apos; x 12&apos;6&quot; · 175 sq ft</span>
        <button type="button" className="text-xs font-semibold text-primary hover:underline">
          Edit
        </button>
      </div>
    </div>
  )
}
