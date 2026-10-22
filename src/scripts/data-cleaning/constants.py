"""Paths, column names and cleaning rules for the gold-standard data cleaning."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_SHEET = REPO_ROOT / "src" / "resources" / "CDR_policy_sheet.xlsx"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "processed"

OUTPUT_XLSX = "CDR_policy_sheet_clean.xlsx"
OUTPUT_CSV = "gold_standard_clean.csv"
OUTPUT_COUNTRY_SUMMARY = "country_summary.csv"
OUTPUT_REPORT = "cleaning_report.md"

SHEET_README = "ReadMe"
SHEET_CODING_SCHEME = "CodingScheme"
SHEET_DATA = "Data"
CSV_ENCODING = "utf-8-sig"

# Columns without content in the source sheet.
DROP_COLUMNS = ["Column1", "Column2"]

# The Excel still uses the old "ETS_" names; codebook v1.0 uses "compliance_".
# Codebook v1.0 is treated as authoritative (project plan, assumption A1).
RENAME_COLUMNS = {
    "ETS_market_type": "compliance_market_type",
    "ETS_upper_bound": "compliance_upper_bound",
    "ETS_upper_bound_unit": "compliance_upper_bound_unit",
}

# Data column -> column in the CodingScheme sheet that lists its allowed values.
CLOSED_FIELDS = {
    "Policy_scope": "Policy_scope",
    "Broad_method": "Broad_method",
    "Specific_method": "Specific_method",
    "Value_chain_focus": "Value_chain_focus",
    "Instrument_broad": "Instrument_broad",
    "Instrument_type": "Instrument_type",
    "compliance_market_type": "Compliance_market_type",
    "Target_type": "Target_type",
    "Target_binding": "Target_binding",
}
MULTI_VALUE_FIELDS = ["Years_amended", "Broad_method", "Specific_method", "Instrument_type"]
# Target fields can hold several targets in parallel ("2030; 2050" / "43; 0").
PARALLEL_LIST_FIELDS = ["Target_year", "Target_amount", "Target_unit"]

VALUE_SEPARATOR = "; "

# Funding units -> (ISO currency code, multiplier to the absolute amount).
FUNDING_UNIT_MAP = {
    "€": ("EUR", 1),
    "EUR": ("EUR", 1),
    "€ million": ("EUR", 1_000_000),
    "EUR million": ("EUR", 1_000_000),
    "USD": ("USD", 1),
    "USD million": ("USD", 1_000_000),
    "AUD": ("AUD", 1),
    "AUD million": ("AUD", 1_000_000),
    "CAD": ("CAD", 1),
    "CAD million": ("CAD", 1_000_000),
    "GBP": ("GBP", 1),
    "JPY": ("JPY", 1),
    "CNY": ("CNY", 1),
    "INR": ("INR", 1),
}

# Query parameters that only track clicks and do not change the document.
TRACKING_PARAMS = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content")

# Short coder initials used in the Validation column -> full names from the codebook author list.
CODER_ALIASES = {
    "LT": "Leona Tenkhoff",
    "LV": "Lisa Voigt",
}

# Tags the expert team used at the start of a comment, e.g. "[NEW ROW: ...]".
COMMENT_TAG_PATTERN = r"\[(NEW ROW|CORRECTED|VCF)\b"

# Added columns
COL_POLICY_ID = "policy_id"
COL_SHEET_ROW = "sheet_row"
COL_CODERS = "coders"
COL_N_CODERS = "n_coders"
COL_DOUBLE_CODED = "double_coded"
COL_COMMENT_TAGS = "comment_tags"
COL_SHARED_DOC_GROUP = "shared_document_group"
COL_N_TARGETS = "n_targets"
COL_FUNDING_RAW = "Funding_raw"
COL_ISSUES = "cleaning_issues"
