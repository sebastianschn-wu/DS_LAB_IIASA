"""Make the benchmark modules importable in the tests (the script name has a dot)."""

import sys
from pathlib import Path

BENCHMARK_DIR = Path(__file__).resolve().parents[1]
if str(BENCHMARK_DIR) not in sys.path:
    sys.path.insert(0, str(BENCHMARK_DIR))
