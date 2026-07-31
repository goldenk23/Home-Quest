"""Phase 3: the existing comb engine registered as a strategy (not rewritten).

The comb strategy is unusual in that ``layout_engine.build_layout`` already emits a full
native layout from a *program*, so this wrapper compiles the ``DesignSpec`` back into that
program and returns the finished layout directly via a pre-built ``LayoutCandidate`` (see
``ai_client``), keeping comb byte-for-byte compatible as the fallback. It is registered here
only so it appears in the strategy list; the multi pipeline special-cases it.
"""
from __future__ import annotations

from ..planner import PlannerContext, TopologyCandidate, register


@register("comb")
def comb_strategy(ctx: PlannerContext) -> TopologyCandidate | None:
    # The comb engine builds native geometry directly from a program rather than from
    # PlacedRoom rectangles, so it does not participate in the PlacedRoom->native_builder
    # flow. ai_client invokes build_layout for the "comb" id; returning None here keeps the
    # registry honest (comb exists) without forcing a second geometry path.
    return None
