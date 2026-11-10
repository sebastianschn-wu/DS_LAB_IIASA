#!/usr/bin/env python3
"""One-/few-shot coding with the unchanged first loop.

Runs ``src/scripts/first-loop/first-loop.script.py`` exactly as it is, with two
additions:

1. ``--shots N`` worked expert examples are appended to the codebook instructions.
2. Only the test policies of ``src/resources/train_test_split.csv`` are coded,
   so zero-shot and few-shot runs are compared on the same policies and no
   example policy (all from the train part) is ever evaluated.

All other options (--model, --max-doc-tokens, --limit, --force, ...) are passed
to the first loop unchanged.

Usage:
    python src/scripts/few-shot/few-shot.script.py --shots 1 --model qwen2.5:7b
    python src/scripts/few-shot/few-shot.script.py --shots 3 --model qwen2.5:7b
    # -> results/shots1_test_coding.csv, results/shots3_test_coding.csv
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
FIRST_LOOP = REPO_ROOT / "src" / "scripts" / "first-loop" / "first-loop.script.py"
DEFAULT_SPLIT_FILE = REPO_ROOT / "src" / "resources" / "train_test_split.csv"
RESULTS_DIR = REPO_ROOT / "results"

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from examples import EXAMPLE_ROWS, SPLIT_TEST, SHEET_ROW, read_split, render_examples, select_examples  # noqa: E402


def load_first_loop():
    spec = importlib.util.spec_from_file_location("first_loop", FIRST_LOOP)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--shots", type=int, required=True, help=f"Number of examples (0-{len(EXAMPLE_ROWS)})")
    parser.add_argument("--split-file", type=Path, default=DEFAULT_SPLIT_FILE)
    args, first_loop_args = parser.parse_known_args(sys.argv[1:] if argv is None else argv)
    if "--output" not in first_loop_args:
        first_loop_args += ["--output", str(RESULTS_DIR / f"shots{args.shots}_test_coding.csv")]

    first_loop = load_first_loop()
    split = read_split(args.split_file)
    examples: list[dict[str, str]] = []
    original_load_policies = first_loop.load_policies
    original_build_instructions = first_loop.build_instructions

    def load_test_policies(path: Path) -> list[dict[str, str]]:
        policies = original_load_policies(path)
        examples[:] = select_examples(policies, args.shots)
        test = [p for p in policies if split.get(p[SHEET_ROW]) == SPLIT_TEST]
        print(f"Few-shot: {len(examples)} example(s), coding {len(test)} test policies")
        for policy in examples:
            print(f"    example: row {policy[SHEET_ROW]} {policy.get('Jurisdiction', '')} | "
                  f"{policy.get('Document_full_title', '')}")
        return test

    def build_instructions_with_examples(prose, definitions, allowed) -> str:
        return original_build_instructions(prose, definitions, allowed) + render_examples(
            examples, first_loop.MODEL_FIELDS
        )

    # The first loop runs unchanged; only these two steps get the few-shot additions.
    first_loop.load_policies = load_test_policies
    first_loop.build_instructions = build_instructions_with_examples
    first_loop.main(first_loop_args)


if __name__ == "__main__":
    main()
