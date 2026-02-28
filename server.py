#!/usr/bin/env python3
"""
Convenience launcher — delegates to the stdb_viewer package.

Usage:
    python server.py                         # serve all .db in current dir
    python server.py -d mydata.db -p 9000    # specific db + port
"""

import sys
from pathlib import Path

# Ensure the package is importable when running directly from the repo
# (i.e. `python server.py` without pip-installing the package first)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from stdb_viewer.__main__ import main

if __name__ == "__main__":
    main()