"""Planner strategy package.

Importing this package registers every strategy in ``planner._REGISTRY`` as a side effect,
so ``ai_client`` only needs ``import generate_layout.planners`` to make the multi-strategy
pipeline aware of comb, subdivision, and the topology variants.
"""
from __future__ import annotations

from . import comb, constraint_solver, rectilinear, subdivision  # noqa: F401 - imported for registration side effects
