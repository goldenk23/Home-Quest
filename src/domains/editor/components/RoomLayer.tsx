import React from 'react';
import { useAppStore } from '@/store';
import { useShallow } from 'zustand/react/shallow';
import { ROOM_FILL_COLORS } from '../constants';
import type { RoomType } from '@/types/editor';

/**
 * ============================================================================
 * WHAT IS THIS FILE FOR?
 * ============================================================================
 * 
 * This file is responsible for drawing all the Rooms (like Bedrooms and Kitchens)
 * onto the 2D floor plan.
 * 
 * THE MENTAL MODEL:
 * 
 * 1. THE DATA (IDs): In our global store, a "Room" is just a list of Vertex IDs 
 *    (the corners of the room) and a Room Type (e.g., "bathroom").
 * 
 * 2. THE MATH (Polygon): We look up those Vertex IDs in the store to find their 
 *    actual X and Y coordinates. This turns the room into a connect-the-dots 
 *    math shape called a Polygon.
 * 
 * 3. THE DRAWING (SVG): We pass those coordinates to an SVG `<polygon>` element,
 *    which automatically connects the dots and colors the inside. We choose the 
 *    color by looking up the Room Type in our ROOM_FILL_COLORS paint palette!
 * 
 * (As always, we flip the Y coordinates mathematically (-y) so the rooms draw 
 * correctly on the web page).
 * 
 * DIAGRAM: HOW ROOMS ARE RENDERED
 *
 * To view a visual flowchart of this pipeline, simply Ctrl+Click 
 * the link below to open it in Mermaid Live Editor:
 * 
 * https://mermaid.live/view#base64:eyJjb2RlIjoiZ3JhcGggVERcbiAgICBjbGFzc0RlZiBzdGF0ZSBmaWxsOiM0ZjQ2ZTUsc3Ryb2tlOiMzMTJlODEsc3Ryb2tlLXdpZHRoOjJweCxjb2xvcjojZmZmXG4gICAgY2xhc3NEZWYgbG9naWMgZmlsbDojMTBiOTgxLHN0cm9rZTojMDY0ZTNiLHN0cm9rZS13aWR0aDoycHgsY29sb3I6I2ZmZlxuICAgIGNsYXNzRGVmIHN2ZyBmaWxsOiNmNTllMGIsc3Ryb2tlOiM3ODM1MGYsc3Ryb2tlLXdpZHRoOjJweCxjb2xvcjojZmZmXG5cbiAgICBzdWJncmFwaCBTdGVwMSBbXCJTdGVwIDE6IFRoZSBTdG9yZSBEYXRhIChJRHMpXCJdXG4gICAgICAgIFMxW1wiUm9vbSBEYXRhPGJyLz4oUm9vbSBUeXBlOiAnYmVkcm9vbScpXCJdOjo6c3RhdGVcbiAgICAgICAgUzJbXCJCb3VuZGFyeSBWZXJ0ZXggSURzPGJyLz4oZS5nLiwgW3YxLCB2MiwgdjMsIHY0XSlcIl06OjpzdGF0ZVxuICAgIGVuZFxuXG4gICAgc3ViZ3JhcGggU3RlcDIgW1wiU3RlcCAyOiBDb29yZGluYXRlIExvb2t1cFwiXVxuICAgICAgICBMMVtcIkxvb2kycCBJRHMgaW4gU3RvcmVcIl06Ojpsb2dpY1xuICAgICAgICBMMltcIkNvbnZlcnQgdG8gcmVhbCBjb29yZGluYXRlczo8YnIvPlt7eCwgeX0sIHt4LCB5fSwgLi4uXVwiXTo6OmxvZ2ljXG4gICAgICAgIEwxIC0tPiBMMlxuICAgIGVuZFxuXG4gICAgc3ViZ3JhcGggU3RlcDMgW1wiU3RlcCAzOiBTVkcgUmVuZGVyaW5nXCJdXG4gICAgICAgIFYxW1wiQnVpbGQgUG9pbnRzIFN0cmluZzxici8+J3gxLC15MSB4MiwieTIgLi4uJ1wiXTo6OnN2Z1xuICAgICAgICBWMltcIkxvb2t1cCBDb2xvcjxici8+KFJPT01fRklMTF9DT0xPUlMpXCJdOjo6c3ZnXG4gICAgICAgIFYzW1wiRHJhdyAmbHQ7cG9seWdvbiZndDtcIl06OjpzdmdcbiAgICAgICAgVjEgLS0+IFYzXG4gICAgICAgIFYyIC0tPiBWM1xuICAgIGVuZFxuXG4gICAgUzEgLS0+IFYyXG4gICAgUzIgLS0+IEwxXG4gICAgTDIgLS0+IFYxIiwibWVybWFpZCI6IntcInRoZW1lXCI6IFwiZGVmYXVsdFwifSIsImF1dG9TeW5jIjp0cnVlLCJ1cGRhdGVEaWFncmFtIjp0cnVlfQ==
 * ============================================================================
 */
export const RoomLayer: React.FC = React.memo(() => {
  // Grab rooms and their actual vertex coordinates from the store
  const rooms = useAppStore(useShallow((state) => {
    return Object.values(state.rooms).map((room) => ({
      id: room.id,
      roomType: room.roomType,
      polygon: room.boundaryVertexIds.map(
        (vid) => state.vertices[vid]?.position ?? { x: 0, y: 0 }
      ),
    }));
  }));

  return (
    <g className="room-layer">
      {rooms.map((room) => {
        // SVG polygons need a single string of coordinates: "x1,y1 x2,y2 ..."
        // Note: We flip the Y-axis (-p.y) so it renders correctly in SVG!
        const pointsString = room.polygon
          .map((p) => `${p.x},${-p.y}`)
          .join(' ');

        return (
          <polygon
            key={room.id}
            points={pointsString}
            fill={ROOM_FILL_COLORS[room.roomType as RoomType] || ROOM_FILL_COLORS.custom}
            // data-entity tags let us easily click and select the room later
            data-entity-id={room.id}
            data-entity-type="room"
          />
        );
      })}
    </g>
  );
});

RoomLayer.displayName = 'RoomLayer';