"""Make the prompt-optimization modules importable in the tests (the scripts have hyphens or dots in their names)."""

import sys
from pathlib import Path

BASELINE_DIR = Path(__file__).resolve().parents[1]
PROMPT_DIR = BASELINE_DIR.parent / "prompt-optimization"
for path in (BASELINE_DIR, PROMPT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
