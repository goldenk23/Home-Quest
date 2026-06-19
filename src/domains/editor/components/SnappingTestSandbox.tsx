import { useRef, useState, Fragment } from 'react';
import type { MouseEvent, FC } from 'react';
import { screenToWorld, worldToScreen } from '../services/geometry';
import { applySnapping } from '../hooks/useSnapping';
import type { Point2D, ViewTransform } from '../../../types/geometry';

// Some hardcoded endpoints we can try snapping to
const DUMMY_ENDPOINTS: Point2D[] = [
  { x: 100, y: 100 },
  { x: -50, y: 50 },
  { x: 0, y: -80 }
];

// A static camera view: 1x scale, centered in an 800x600 canvas
const DEFAULT_VIEW: ViewTransform = {
  scale: 1, 
  offsetX: 400, 
  offsetY: 300  
};

export const SnappingTestSandbox: FC = () => {
  const svgRef = useRef<SVGSVGElement>(null);
  
  const [rawMouseWorld, setRawMouseWorld] = useState<Point2D>({ x: 0, y: 0 });
  const [snappedMouseWorld, setSnappedMouseWorld] = useState<Point2D>({ x: 0, y: 0 });
  
  const [gridEnabled, setGridEnabled] = useState(true);
  const [endpointEnabled, setEndpointEnabled] = useState(true);

  const handleMouseMove = (e: MouseEvent<SVGSVGElement>) => {
    if (!svgRef.current) return;
    
    // Get the exact bounding box of the SVG on the screen
    const rect = svgRef.current.getBoundingClientRect();
    const screenPoint = { px: e.clientX, py: e.clientY };
    
    // 1. Convert actual screen mouse pixels into our 2D World coordinates
    const worldPt = screenToWorld(screenPoint, rect, DEFAULT_VIEW);
    setRawMouseWorld(worldPt);

    // 2. Pass those world coordinates into your snapping hook!
    const snappedPt = applySnapping(worldPt, DUMMY_ENDPOINTS, {
      gridSize: 20, // 20cm grid
      snapRadius: 30, // snap to endpoint if within 30cm
      gridSnapEnabled: gridEnabled,
      endpointSnapEnabled: endpointEnabled
    });
    setSnappedMouseWorld(snappedPt);
  };

  // Helper to convert world coordinates back into SVG-relative pixel coordinates for rendering
  const renderPoint = (worldPt: Point2D) => {
    // We pass left:0 and top:0 because SVG cx/cy attributes are relative to the SVG itself, not the browser window.
    const dummyRect = { left: 0, top: 0, width: 800, height: 600 } as DOMRect;
    return worldToScreen(worldPt, dummyRect, DEFAULT_VIEW);
  };

  const rawScreen = renderPoint(rawMouseWorld);
  const snappedScreen = renderPoint(snappedMouseWorld);

  return (
    <div style={{ display: 'flex', gap: '2rem' }}>
      <div>
        <svg 
          ref={svgRef}
          width={800} 
          height={600} 
          style={{ border: '2px solid #333', backgroundColor: '#fff', cursor: 'crosshair', borderRadius: '8px' }}
          onMouseMove={handleMouseMove}
        >
          {/* Draw a 20px grid background to visualize the gridSize */}
          <g stroke="#f0f0f0" strokeWidth="1">
            {Array.from({length: 40}).map((_, i) => (
              <Fragment key={i}>
                <line x1={i*20} y1={0} x2={i*20} y2={600} />
                <line x1={0} y1={i*20} x2={800} y2={i*20} />
              </Fragment>
            ))}
          </g>
          
          {/* X and Y Axis lines crossing at the origin (0,0) */}
          <line x1={400} y1={0} x2={400} y2={600} stroke="#cbd5e1" strokeWidth="2" />
          <line x1={0} y1={300} x2={800} y2={300} stroke="#cbd5e1" strokeWidth="2" />

          {/* Draw our Dummy Endpoints */}
          {DUMMY_ENDPOINTS.map((pt, i) => {
            const sp = renderPoint(pt);
            return (
              <g key={i}>
                {/* Visualizing the snap radius */}
                <circle cx={sp.px} cy={sp.py} r={30} fill="rgba(59, 130, 246, 0.1)" stroke="#3b82f6" strokeDasharray="4" />
                <circle cx={sp.px} cy={sp.py} r={6} fill="#3b82f6" />
              </g>
            )
          })}

          {/* The Raw Mouse Position */}
          <circle cx={rawScreen.px} cy={rawScreen.py} r={4} fill="rgba(0,0,0,0.3)" />

          {/* A line connecting raw to snapped */}
          <line x1={rawScreen.px} y1={rawScreen.py} x2={snappedScreen.px} y2={snappedScreen.py} stroke="#ef4444" strokeDasharray="4" />

          {/* The Snapped Position */}
          <circle cx={snappedScreen.px} cy={snappedScreen.py} r={6} fill="#ef4444" />
        </svg>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', width: '300px' }}>
        <div style={{ padding: '1rem', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
          <h3 style={{ marginTop: 0, fontSize: '1rem' }}>Snap Configuration</h3>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', marginBottom: '8px' }}>
            <input type="checkbox" checked={gridEnabled} onChange={e => setGridEnabled(e.target.checked)} /> 
            Grid Snap (20cm)
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
            <input type="checkbox" checked={endpointEnabled} onChange={e => setEndpointEnabled(e.target.checked)} /> 
            Endpoint Snap (30cm radius)
          </label>
        </div>

        <div style={{ padding: '1rem', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0', fontFamily: 'monospace' }}>
          <h3 style={{ marginTop: 0, fontSize: '1rem', fontFamily: 'sans-serif' }}>World Coordinates</h3>
          <div style={{ color: '#64748b' }}>
            Raw: <br/>
            X: {rawMouseWorld.x.toFixed(1)} <br/>
            Y: {rawMouseWorld.y.toFixed(1)}
          </div>
          <hr style={{ borderColor: '#e2e8f0', margin: '8px 0' }} />
          <div style={{ color: '#ef4444', fontWeight: 'bold' }}>
            Snapped: <br/>
            X: {snappedMouseWorld.x.toFixed(1)} <br/>
            Y: {snappedMouseWorld.y.toFixed(1)}
          </div>
        </div>
      </div>
    </div>
  );
}
