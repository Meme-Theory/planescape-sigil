"""dc_suggest — the Typical Difficulty Classes ladder, cited per view."""

from __future__ import annotations

from typing import Any

from . import tables


def dc_suggest(difficulty: str | None = None, view: str = "5e-2014") -> dict[str, Any]:
    """The DC ladder (or one rung), with the page citation for the active view.

    Values are identical across 5e-2014/5e-2024; the *citation* differs, and a
    Mechanus answer never ships without one.
    """
    if view not in tables.VIEWS_5E:
        raise ValueError(f"no DC ladder for view {view!r} — 2e tasks are roll-under ability checks (Modron's pack handles the dice)")
    ladder = tables.dc_ladder()
    out: dict[str, Any] = {"view": view, "source": tables.dc_source(view), "law_version": tables.law_version()}
    if difficulty is None:
        out["ladder"] = ladder
        return out
    want = difficulty.strip().lower()
    for rung in ladder:
        if rung["task"].lower() == want:
            out.update(rung)
            return out
    raise ValueError(f"unknown difficulty {difficulty!r}; ladder: {[r['task'] for r in ladder]}")
