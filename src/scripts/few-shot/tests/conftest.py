"""Make the few-shot modules importable in the tests (the folder name has a hyphen)."""

import sys
from pathlib import Path

FEW_SHOT_DIR = Path(__file__).resolve().parents[1]
if str(FEW_SHOT_DIR) not in sys.path:
    sys.path.insert(0, str(FEW_SHOT_DIR))
