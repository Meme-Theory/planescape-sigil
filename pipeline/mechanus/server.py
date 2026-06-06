"""Launcher — uniform with Modron's layout so .mcp.json entries match shape."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mechanus.server import main

if __name__ == "__main__":
    asyncio.run(main())
