import React from 'react';

interface GridLayerProps {
  /** Grid cell size in world units (cm). */
  gridSize: number;
}

/**
 * ============================================================================
 * WHAT IS THIS FILE FOR?
 * ============================================================================
 * 
 * This file creates the "Infinite Graph Paper" background for the 2D editor.
 * 
 * THE MENTAL MODEL:
 * 
 * Instead of manually drawing thousands of little grid lines which would 
 * crash the browser, we use a classic wallpaper trick:
 * 
 * 1. THE TILE (<pattern>): We create one tiny, invisible square (e.g., 20x20cm).
 *    Inside this square, we draw a single, faint white dot in the top-left corner.
 * 
 * 2. THE WALL (<rect>): We create a gigantic invisible rectangle that is 
 *    100,000 centimeters wide and tall. We set `pointerEvents="none"` so that
 *    your mouse clicks pass right through it like a ghost (letting you click 
 *    on the walls and rooms underneath).
 * 
 * 3. THE PAINT (fill="url(#...)"): We tell the browser to "paint" the giant 
 *    wall using our tiny tile. The browser automatically copies and pastes 
 *    that single dot millions of times to fill the space, creating the perfect 
 *    illusion of an infinite dotted grid!
 * 
 * DIAGRAM: HOW THE GRID WORKS
 *
 * To view a visual flowchart of this 3-step process, simply Ctrl+Click 
 * the link below to open it in Mermaid Live Editor:
 * 
 * https://mermaid.live/view#base64:eyJjb2RlIjoiZ3JhcGggVERcbiAgICBjbGFzc0RlZiB0aWxlIGZpbGw6IzFlMjkzYixzdHJva2U6IzYzNjZmMSxzdHJva2Utd2lkdGg6MnB4LGNvbG9yOiNmZmZcbiAgICBjbGFzc0RlZiBjYW52YXMgZmlsbDojMGYxNzJhLHN0cm9rZTojMTBiOTgxLHN0cm9rZS13aWR0aDoycHgsY29sb3I6I2ZmZlxuICAgIGNsYXNzRGVmIG91dHB1dCBmaWxsOiMzYjgyZjYsc3Ryb2tlOiMyNTYzZWIsc3Ryb2tlLXdpZHRoOjJweCxjb2xvcjojZmZmXG5cbiAgICBzdWJncmFwaCBTdGVwMSBbXCJTdGVwIDE6IENyZWF0ZSB0aGUgVGlsZSBQYXR0ZXJuICg8cGF0dGVybj4pXCJdXG4gICAgICAgIFQxW1wiQSBzbWFsbCB0cmFuc3BhcmVudCBzcXVhcmU8YnIvPihlLmcuLCAyMHgyMCBjbSlcIl06Ojp0aWxlXG4gICAgICAgIFQyW1wiRHJhdyBvbmUgdGlueSB3aGl0ZSBkb3Q8YnIvPmF0IHRoZSAoMCwwKSBjb3JuZXJcIl06Ojp0aWxlXG4gICAgICAgIFQxIC0tPiBUMlxuICAgIGVuZFxuXG4gICAgc3ViZ3JhcGggU3RlcDIgW1wiU3RlcCAyOiBDcmVhdGUgYSBNYXNzaXZlIENhbnZhcyAoPHJlY3Q+KVwiXVxuICAgICAgICBDMVtcIkRyYXcgYSBnaWdhbnRpYyBpbnZpc2libGUgcmVjdGFuZ2xlPGJyLz4oMTAwLDAwMCB4IDEwMCwwMDAgY20pXCJdOjo6Y2FudmFzXG4gICAgICAgIEMyW1wiU2V0IHBvaW50ZXItZXZlbnRzIHRvICdub25lJzxici8+c28gbW91c2UgY2xpY2tzIHBhc3MgcmlnaHQgdGhyb3VnaCBpdFwiXTo6OmNhbnZhc1xuICAgICAgICBDMSAtLT4gQzJcbiAgICBlbmRcblxuICAgIHN1YmdyYXBoIFN0ZXAzIFtcIlN0ZXAgMzogUGFpbnQgYW5kIFJlcGVhdCFcIl1cbiAgICAgICAgUjFbXCJVc2UgdGhlIFRpbGUgUGF0dGVybiBhczxici8+dGhlICdwYWludCcgZm9yIHRoZSBDYW52YXNcIl06OjpvdXRwdXRcbiAgICAgICAgUjJbXCJUaGUgYnJvd3NlciBhdXRvbWF0aWNhbGx5IGNvcGllcyBhbmQgcGFzdGVzPGJyLz50aGUgdGlsZSBtaWxsaW9ucyBvZiB0aW1lcyB0byBmaWxsIHRoZSBjYW52YXMhXCJdOjo6b3V0cHV0XG4gICAgICAgIFIxIC0tPiBSMlxuICAgIGVuZFxuXG4gICAgU3RlcDEgLS0+IFN0ZXAzXG4gICAgU3RlcDIgLS0+IFN0ZXAzIiwibWVybWFpZCI6IntcInRoZW1lXCI6IFwiZGVmYXVsdFwifSIsImF1dG9TeW5jIjp0cnVlLCJ1cGRhdGVEaWFncmFtIjp0cnVlfQ==
 * ============================================================================
 */
export const GridLayer: React.FC<GridLayerProps> = React.memo(({ gridSize }) => {
  const patternId = 'editor-grid-pattern';
  return (
    <>
      <defs>
        <pattern id={patternId} width={gridSize} height={gridSize} patternUnits="userSpaceOnUse">
          <circle cx={0} cy={0} r={0.5} fill="rgba(255,255,255,0.15)" />
        </pattern>
      </defs>
      <rect
        x={-50000}
        y={-50000}
        width={100000}
        height={100000}
        fill={`url(#${patternId})`}
        pointerEvents="none"
      />
    </>
  );
});

GridLayer.displayName = 'GridLayer';
