"""Mechanus — the rules engine. Mimir remembers, Mechanus rules, Modron rolls.

The plane of absolute law: invoke rules, arbitrate conflicts, manifest objects
across editions. This package is the mechanical core + rulings ledger; the law
*data* lives in data/law/*.json, every table cited to a page of something we
legitimately hold. Design doc: pipeline/mimir/MECHANUS.md.
"""

from .tables import law_version, cr_to_xp, cr_to_pb, parse_cr
from .lawful import is_lawful, known_waivers
from .dc import dc_suggest
from .budget import encounter_budget

CORE_VERSION = "0.1"  # mechanical core; law data carries its own content-address

__all__ = [
    "CORE_VERSION", "law_version",
    "is_lawful", "known_waivers", "dc_suggest", "encounter_budget",
    "cr_to_xp", "cr_to_pb", "parse_cr",
]
