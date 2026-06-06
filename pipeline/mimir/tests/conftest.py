"""Put pipeline/mimir on sys.path so tests import the store/gate as the server does.

gate.py inserts its own deps (pipeline/parse for normalize) at import time; we only
need to reach gate.py and store.py themselves.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))            # pipeline/mimir
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "parse"))  # pipeline/parse (extractor)
