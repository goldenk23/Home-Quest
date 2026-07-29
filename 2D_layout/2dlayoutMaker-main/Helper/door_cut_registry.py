from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


Interval = Tuple[float, float]


@dataclass
class DoorCutRegistry:
    """
    Stores and merges door cut intervals per room and wall side.

    - Keyed by `room_group_tag` (e.g. "room_group_1001")
    - Each side ("top", "bottom", "left", "right") stores a merged list of intervals.
    - Intervals are in absolute canvas coordinates along the wall axis:
        - top/bottom: x positions
        - left/right: y positions
    """

    _cuts: Dict[str, Dict[str, List[Interval]]] = field(default_factory=dict)
    _eps: float = 0.75  # px tolerance to merge nearly-touching intervals

    def clear_room(self, room_group_tag: str) -> None:
        try:
            self._cuts.pop(room_group_tag, None)
        except Exception:
            pass

    def clear_all(self) -> None:
        try:
            self._cuts.clear()
        except Exception:
            pass

    def get_merged(self, room_group_tag: str, wall_side: str) -> List[Interval]:
        room = self._cuts.get(room_group_tag) or {}
        return list(room.get(wall_side) or [])

    def add_cut(
        self,
        room_group_tag: str,
        wall_side: str,
        start: float,
        end: float,
        *,
        wall_min: float,
        wall_max: float,
    ) -> List[Interval]:
        """
        Add a cut interval and return the merged interval list for this wall.
        """
        try:
            s = float(start)
            e = float(end)
            w0 = float(min(wall_min, wall_max))
            w1 = float(max(wall_min, wall_max))
        except Exception:
            return self.get_merged(room_group_tag, wall_side)

        if s > e:
            s, e = e, s

        # Clamp to the wall span
        s = max(w0, min(s, w1))
        e = max(w0, min(e, w1))
        if e - s <= self._eps:
            return self.get_merged(room_group_tag, wall_side)

        room_map = self._cuts.setdefault(room_group_tag, {})
        arr = list(room_map.get(wall_side) or [])
        arr.append((s, e))
        merged = self._merge_intervals(arr)
        room_map[wall_side] = merged
        return list(merged)

    def _merge_intervals(self, intervals: List[Interval]) -> List[Interval]:
        if not intervals:
            return []

        data = []
        for s, e in intervals:
            try:
                s = float(s)
                e = float(e)
            except Exception:
                continue
            if e < s:
                s, e = e, s
            data.append((s, e))

        if not data:
            return []

        data.sort(key=lambda t: t[0])
        merged: List[Interval] = []
        cur_s, cur_e = data[0]
        for s, e in data[1:]:
            if s <= cur_e + self._eps:
                cur_e = max(cur_e, e)
            else:
                merged.append((cur_s, cur_e))
                cur_s, cur_e = s, e
        merged.append((cur_s, cur_e))
        return merged

