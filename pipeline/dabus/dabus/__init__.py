"""dabus — the voice engine (Mimir remembers, Mechanus rules, Modron rolls, dabus speaks).

The silent servitor taught to talk: an MCP over the tools/ F5-TTS voice stack.
Design doc: pipeline/dabus/DABUS.md. Boundary: dabus PERFORMS — it judges no
law, rolls no dice, and every render is stamped local-only (PST audio + CC-BY-NC
checkpoints never ship).
"""

from pathlib import Path

ENGINE_VERSION = "1"  # bump on any change to the render derivation or cache-key canon

PKG_DIR = Path(__file__).resolve().parent
REPO = PKG_DIR.parent.parent.parent          # pipeline/dabus/dabus -> repo root
VOICES_DIR = REPO / "tools" / "voices"       # voice packs (*.toml) + rip folders
BUILD_DIR = REPO / "build" / "dabus"         # mutable store (family law)
RENDERS_DIR = BUILD_DIR / "renders"
DB_PATH = BUILD_DIR / "renders.db"

LANE = "local-only (PST audio + living actors + CC-BY-NC F5 checkpoints — never ships)"

DEFAULT_MODEL = "F5TTS_v1_Base"
