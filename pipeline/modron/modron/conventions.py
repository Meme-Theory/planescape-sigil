"""Convention packs — edition is a view, for dice too (MODRON.md §5).

A pack is DATA (data/conventions/<view>.json): how attacks/saves/checks/morale
resolve, how the d20 state machine composes, what a crit does, how division
rounds. New edition or house variant = a JSON drop-in or an overlay — no code.

Overlays (data/overrides/<view>.json) deep-merge over packs and are always
disclosed in pack['_overlays'] — a hidden house rule is not a house rule.
When Mechanus pours rulings.db, scoped rulings that carry dice-convention
payloads will join the overlay chain (MODRON.md §2.2); the merge law is
already here.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent
CONVENTIONS_DIR = PACKAGE_DIR / "data" / "conventions"
OVERRIDES_DIR = PACKAGE_DIR / "data" / "overrides"


class UnknownView(KeyError):
    pass


def _deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_views() -> list[str]:
    if not CONVENTIONS_DIR.exists():
        return []
    return sorted(p.stem for p in CONVENTIONS_DIR.glob("*.json"))


def get_pack(view: str) -> dict:
    """Load a convention pack + its overlay chain. Raises UnknownView."""
    path = CONVENTIONS_DIR / f"{view}.json"
    if not path.exists():
        raise UnknownView(
            f"no convention pack for view {view!r} (known: {', '.join(list_views()) or 'none'})")
    pack = _load_json(path)

    # extends-chain (e.g. 5e-2024 extends 5e-2014), cycles guarded
    seen = {view}
    base_name = pack.get("extends")
    while base_name:
        if base_name in seen:
            raise ValueError(f"convention pack extends-cycle at {base_name!r}")
        seen.add(base_name)
        base_path = CONVENTIONS_DIR / f"{base_name}.json"
        if not base_path.exists():
            raise UnknownView(f"pack {view!r} extends missing pack {base_name!r}")
        base = _load_json(base_path)
        pack = _deep_merge(base, {k: v for k, v in pack.items() if k != "extends"})
        base_name = base.get("extends")

    overlays = []
    overlay_path = OVERRIDES_DIR / f"{view}.json"
    if overlay_path.exists():
        overlay = _load_json(overlay_path)
        pack = _deep_merge(pack, overlay)
        overlays.append({"file": str(overlay_path), "keys": sorted(overlay.keys())})
    pack["_overlays"] = overlays  # always disclosed
    _validate_pack(pack, view)
    return pack


def _validate_pack(pack: dict, view: str) -> None:
    if pack.get("view") != view:
        raise ValueError(f"pack file {view}.json declares view={pack.get('view')!r}")
    if pack.get("rounding") not in ("down", "up"):
        raise ValueError(f"pack {view}: rounding must be 'down'|'up'")
    if pack.get("crit_effect") not in ("double_dice", "double_total",
                                       "max_dice_plus_roll", "none"):
        raise ValueError(f"pack {view}: unknown crit_effect {pack.get('crit_effect')!r}")
    checks = pack.get("checks", {})
    if not isinstance(checks, dict):
        raise ValueError(f"pack {view}: checks must be an object")
    for kind, spec in checks.items():
        if "roll" not in spec:
            raise ValueError(f"pack {view}: check {kind!r} lacks a roll template")
        if spec.get("success_op") not in (None, ">=", "<="):
            raise ValueError(f"pack {view}: check {kind!r} success_op must be '>='|'<='")


def get_check_spec(view: str, kind: str) -> tuple[dict, dict]:
    """(check spec, pack) for a semantic roll kind. Raises with the menu on miss."""
    pack = get_pack(view)
    checks = pack.get("checks", {})
    if kind not in checks:
        raise KeyError(
            f"view {view!r} defines no check kind {kind!r} "
            f"(available: {', '.join(sorted(checks)) or 'none'})")
    return checks[kind], pack
