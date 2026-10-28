"""Paths, fields and labels for benchmarking LLM codings against the gold standard."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_PREDICTIONS = REPO_ROOT / "results" / "first_loop_coding.csv"
DEFAULT_GOLD = REPO_ROOT / "data" / "processed" / "gold_standard_clean.csv"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "results" / "benchmark"
CSV_ENCODING = "utf-8-sig"

KEY = "sheet_row"
SOURCE = "source_used"
FALLBACK = "fallback_reason"

# Fields with one value per policy.
SINGLE_FIELDS = [
    "Policy_scope",
    "Value_chain_focus",
    "Instrument_broad",
    "Target_type",
    "Target_binding",
    "compliance_market_type",
]
# Fields that can hold several values ("a; b").
MULTI_FIELDS = ["Broad_method", "Specific_method", "Instrument_type", "Years_amended"]
# Free-text field scored with text-similarity metrics.
TEXT_FIELD = "CDR_link"

# Core variables of the codebook used for the headline score.
CORE_FIELDS = [
    "Policy_scope",
    "Broad_method",
    "Specific_method",
    "Value_chain_focus",
    "Instrument_broad",
    "Instrument_type",
]

# Old column names in the raw sheet -> codebook names (in case the raw sheet is used as gold).
GOLD_RENAME = {
    "ETS_market_type": "compliance_market_type",
    "ETS_upper_bound": "compliance_upper_bound",
    "ETS_upper_bound_unit": "compliance_upper_bound_unit",
}

NONE_LABEL = "(none)"
SUBSET_ALL = "all"
SUBSET_DOCUMENT = "document"
SUBSET_SUMMARY = "summary"
SUBSETS = [SUBSET_ALL, SUBSET_DOCUMENT, SUBSET_SUMMARY]

# Output files
OUT_FIELD_METRICS = "field_metrics.csv"
OUT_LABEL_METRICS = "label_metrics.csv"
OUT_CONFUSIONS = "confusions.csv"
OUT_TEXT_METRICS = "text_metrics.csv"
OUT_ROWS = "row_level.csv"
OUT_COUNTRIES = "country_accuracy.csv"
OUT_SUMMARY = "benchmark_summary.md"
OUT_FIGURE = "accuracy_by_source.png"

# Chart colours (validated categorical slots 1 and 2, light surface)
COLOR_DOCUMENT = "#2a78d6"
COLOR_SUMMARY = "#eb6834"
COLOR_SURFACE = "#fcfcfb"
COLOR_TEXT = "#0b0b0b"
COLOR_TEXT_SECONDARY = "#52514e"
COLOR_GRID = "#e4e3df"
