"""Make the first-loop modules importable in the tests (the folder name has a hyphen)."""

import sys
from pathlib import Path

FIRST_LOOP_DIR = Path(__file__).resolve().parents[1]
if str(FIRST_LOOP_DIR) not in sys.path:
    sys.path.insert(0, str(FIRST_LOOP_DIR))
