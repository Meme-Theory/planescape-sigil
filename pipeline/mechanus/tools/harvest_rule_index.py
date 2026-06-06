"""Harvest topic->page indexes from the build/mechanus/*-text caches.

Produces the chapter/anchor maps embedded in the rules-lawyer agent
definitions (.claude/agents/lemure.md, abishai.md). Re-run after a cache
re-pour to re-derive; output is a report to stdout, not a store write.

Usage:  py -3.13 pipeline/mechanus/tools/harvest_rule_index.py
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / "build" / "mechanus"


def pages(slug: str):
    for f in sorted((CACHE / f"{slug}-text").glob("p*.txt")):
        yield int(f.stem[1:]), f.read_text(encoding="utf-8")


def fgg_chapters() -> None:
    print("== FG&G chapter spans (PDF page index) ==")
    spans: dict[str, list[int]] = {}
    rx = re.compile(r"^(CHAPTER \d+|APPENDIX [A-Z])\.? ?(.*)$", re.M)
    for n, text in pages("fgg"):
        for m in rx.finditer(text):
            key, title = m.group(1), m.group(2).strip()
            if title:  # running header with title names the chapter
                spans.setdefault(f"{key}. {title}", []).append(n)
            else:
                spans.setdefault(key, []).append(n)
    # merge bare "CHAPTER N" openers into their titled span
    merged: dict[str, list[int]] = {}
    for key, ns in spans.items():
        base = key.split(".")[0]
        tgt = next((k for k in merged if k.startswith(base + ".")), None)
        if "." not in key and tgt:
            merged[tgt].extend(ns)
        else:
            merged[key] = list(ns)
    for key, ns in sorted(merged.items(), key=lambda kv: min(kv[1])):
        print(f"  pp.{min(ns):>3}-{max(ns):<3}  {key}")


def anchors(slug: str, topics: dict[str, str], max_hits: int = 3) -> None:
    print(f"== {slug} topic anchors ==")
    compiled = {t: re.compile(rx, re.M) for t, rx in topics.items()}
    hits: dict[str, list[int]] = {t: [] for t in topics}
    for n, text in pages(slug):
        for t, rx in compiled.items():
            if len(hits[t]) < max_hits and rx.search(text):
                hits[t].append(n)
    for t, ns in hits.items():
        where = ", ".join(f"p{n}" for n in ns) if ns else "NOT FOUND"
        print(f"  {t:<38} {where}")


fgg_chapters()
anchors("fgg", {
    "saving throws (rules)": r"^SAVING THROWS",
    "saving throw tables (by class)": r"Table 3\.2",
    "THACO advancement (warrior 3.3)": r"Table 3\.3",
    "nonweapon proficiencies": r"^NONWEAPON PROFICIENC",
    "thief skills table": r"Table 3\.3[0-9]|THIEVING SKILL|Thieving Skill",
    "morale (rules)": r"^MORALE\b",
    "encounter reactions": r"ENCOUNTER REACTIONS|^REACTIONS\b",
    "surprise": r"^SURPRISE\b",
    "initiative": r"^INITIATIVE\b",
    "attack rolls / combat procedure": r"^THE ATTACK ROLL|^ATTACK ROLL",
    "turning undead": r"^TURNING UNDEAD|Turning Undead",
    "experience/advancement": r"^EXPERIENCE\b",
    "magic resistance": r"^MAGIC RESISTANCE",
    "psionics": r"^PSIONIC",
    "bestiary start (format guide)": r"^BESTIARY|^MONSTERS\b",
})
anchors("srd51", {
    "Using Ability Scores": r"^Using Ability Scores",
    "Typical DCs ladder": r"Typical DCs",
    "Advantage and Disadvantage": r"^Advantage and Disadvantage",
    "Saving Throws": r"^Saving Throws$",
    "Time / Movement / Environment": r"^Movement$",
    "Order of Combat": r"^The Order of Combat|^Order of Combat",
    "Making an Attack": r"^Making an Attack",
    "Damage and Healing": r"^Damage and Healing",
    "Spellcasting (ch.)": r"^Spellcasting$",
    "Monsters (format intro)": r"^Monsters$",
    "Conditions appendix": r"^Appendix PH-A: Conditions|^Conditions$",
    "Legal / attribution": r"Creative Commons Attribution",
})
anchors("srd52", {
    "Playing the Game": r"^Playing the Game$",
    "DC ladder (Typical DCs)": r"Typical Difficulty Classes|Typical DCs",
    "D20 Tests": r"^D20 Tests",
    "Combat section": r"^Combat$",
    "Spells chapter": r"^Spell Descriptions|^Spells$",
    "Monsters chapter": r"^Monsters( A-Z)?$",
    "Magic Items": r"^Magic Items$",
    "Gameplay Toolbox": r"^Gameplay Toolbox",
    "XP Budget (encounter math)": r"XP Budget",
    "Rules Glossary": r"^Rules Glossary",
    "Legal / attribution": r"Creative Commons Attribution",
})
