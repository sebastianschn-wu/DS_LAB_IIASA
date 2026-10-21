"""Settings, column names, and prompt text for the first coding loop."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_SHEET = REPO_ROOT / "src" / "resources" / "CDR_policy_sheet.xlsx"
DEFAULT_CODEBOOK = REPO_ROOT / "src" / "resources" / "codebook_guidelines.docx"
DEFAULT_OUTPUT = REPO_ROOT / "results" / "first_loop_coding.csv"
SOURCE_CACHE_DIRNAME = "source_cache"

DEFAULT_MODEL = "qwen2.5"
DEFAULT_HOST = "http://127.0.0.1:11434"
DEFAULT_MAX_DOC_TOKENS = 6000
MIN_DOCUMENT_TOKENS = 40
MAX_DOWNLOAD_BYTES = 25_000_000
DOWNLOAD_TIMEOUT = (15, 90)
FETCH_ATTEMPTS = 2

OLLAMA_CONTEXT_CAP = 32768
OLLAMA_CONTEXT_FLOOR = 8192
OLLAMA_CONTEXT_RESERVE = 2048
OLLAMA_CONTEXT_SAFETY_FACTOR = 1.25
OLLAMA_START_TIMEOUT_SECONDS = 60
OLLAMA_TAGS_TIMEOUT = 3
OLLAMA_PULL_CHECK_TIMEOUT = 10
OLLAMA_CHAT_TIMEOUT = 900
OLLAMA_KEEP_ALIVE = "30m"
OLLAMA_SEED = 1
OLLAMA_NUM_PREDICT = 1024
MODEL_CALL_ATTEMPTS = 2

SUMMARY_COLUMN = "CDR_link"
FIELD_YEARS_AMENDED = "Years_amended"

MODEL_FIELDS = [
    FIELD_YEARS_AMENDED,
    "Policy_scope",
    "CDR_link",
    "Broad_method",
    "Specific_method",
    "Value_chain_focus",
    "Instrument_broad",
    "Instrument_type",
    "compliance_market_type",
    "compliance_upper_bound",
    "compliance_upper_bound_unit",
    "Target_year",
    "Target_amount",
    "Target_unit",
    "Target_type",
    "Target_binding",
    "Funding_sum",
    "Funding_unit",
    "Comments",
]

MULTI_VALUE_FIELDS = {
    FIELD_YEARS_AMENDED,
    "Broad_method",
    "Specific_method",
    "Instrument_type",
}

ALLOWED_COLUMN_MAP = {
    "Policy_scope": "Policy_scope",
    "Broad_method": "Broad_method",
    "Specific_method": "Specific_method",
    "Value_chain_focus": "Value_chain_focus",
    "Instrument_broad": "Instrument_broad",
    "Instrument_type": "Instrument_type",
    "Compliance_market_type": "compliance_market_type",
    "compliance_upper_bound_unit": "compliance_upper_bound_unit",
    "Target_unit": "Target_unit",
    "Target_type": "Target_type",
    "Target_binding": "Target_binding",
    "Funding_unit": "Funding_unit",
}

CLOSED_FIELDS = {
    "Policy_scope",
    "Broad_method",
    "Specific_method",
    "Value_chain_focus",
    "Instrument_broad",
    "Instrument_type",
    "compliance_market_type",
    "Target_type",
    "Target_binding",
}

OPEN_UNIT_FIELDS = {
    "compliance_upper_bound_unit",
    "Target_unit",
    "Funding_unit",
}

COL_SHEET_ROW = "sheet_row"
COL_JURISDICTION = "Jurisdiction"
COL_ISO = "Iso"
COL_DOCUMENT_TITLE = "Document_full_title"
COL_YEAR_ENACTED = "Year_enacted"
COL_LINK = "Link"
COL_MODEL = "model"
COL_SOURCE_USED = "source_used"
COL_FALLBACK_REASON = "fallback_reason"
COL_OMIT_REASON = "omit_reason"
COL_DOCUMENT_TOKENS = "document_tokens"
COL_TOKENS_LOWER_BOUND = "tokens_lower_bound"
COL_FETCH_ERROR = "fetch_error"
COL_MODEL_ERROR = "model_error"
COL_CODED_AT = "coded_at"
COL_VALIDATION_NOTES = "validation_notes"

IDENTITY_COLUMNS = [
    COL_SHEET_ROW,
    COL_JURISDICTION,
    COL_ISO,
    COL_DOCUMENT_TITLE,
    COL_YEAR_ENACTED,
    COL_LINK,
]

RUN_COLUMNS = [
    COL_MODEL,
    COL_SOURCE_USED,
    COL_FALLBACK_REASON,
    COL_OMIT_REASON,
    COL_DOCUMENT_TOKENS,
    COL_TOKENS_LOWER_BOUND,
    COL_FETCH_ERROR,
    COL_MODEL_ERROR,
    COL_CODED_AT,
    COL_VALIDATION_NOTES,
]

SHEET_DATA = "Data"
SHEET_CODING_SCHEME = "CodingScheme"
CODEBOOK_DOCUMENT_XML = "word/document.xml"
CODEBOOK_VARIABLE_HEADER = "Variable name"
WORDPROCESSING_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
CODEBOOK_PROSE_HEADINGS = (
    "Definition of Policy",
    "Unit of Analysis",
    "Coding Approach",
    "Revisions and Document Families",
)

USER_AGENT = (
    "CDR-Policy-Coder/1.0 (IIASA research; local first-loop coding; +https://iiasa.ac.at)"
)
HTTP_ACCEPT = "text/html,application/pdf,*/*;q=0.8"
CSV_ENCODING = "utf-8-sig"
TEXT_ENCODING = "utf-8"
HTML_PARSER = "html.parser"
PDF_EXTENSION = ".pdf"
PDF_MAGIC = b"%PDF"

VALUE_SEPARATOR = "; "
EMPTY_MODEL_VALUES = frozenset({"null", "none", "n/a", "na", "unknown", "not stated", "-"})
OTHER_LABEL = "other"
TOKENS_LOWER_BOUND_YES = "yes"
TOKENS_LOWER_BOUND_NO = "no"

OUTCOME_OK = "ok"
OUTCOME_OVER_THRESHOLD = "over_threshold"
OUTCOME_EMPTY = "empty"
OUTCOME_ERROR = "error"
CACHEABLE_OUTCOMES = {OUTCOME_OK, OUTCOME_OVER_THRESHOLD, OUTCOME_EMPTY}

FETCH_OUTCOME = "outcome"
FETCH_TOKENS = "tokens"
FETCH_TOKENS_LOWER_BOUND = "tokens_lower_bound"
FETCH_TEXT = "text"
FETCH_ERROR = "error"

SOURCE_DOCUMENT = "document"
SOURCE_SUMMARY = "summary"
SOURCE_OMITTED = "omitted"
SOURCE_ERROR = "error"
COMPLETE_SOURCES = {SOURCE_DOCUMENT, SOURCE_SUMMARY, SOURCE_OMITTED}

FALLBACK_OVER_TOKEN_THRESHOLD = "over_token_threshold"
FALLBACK_EMPTY_DOCUMENT = "empty_document"
FALLBACK_FETCH_FAILED = "fetch_failed"
OMIT_REASON_SUFFIX = "_and_no_summary"
FALLBACK_BY_OUTCOME = {
    OUTCOME_OVER_THRESHOLD: FALLBACK_OVER_TOKEN_THRESHOLD,
    OUTCOME_EMPTY: FALLBACK_EMPTY_DOCUMENT,
    OUTCOME_ERROR: FALLBACK_FETCH_FAILED,
}

MISSING_LINK_ERROR = "missing link"
ENCRYPTED_PDF_ERROR = "encrypted PDF"
JSON_OBJECT_ERROR = "model response JSON was not an object"
OLLAMA_MISSING_MESSAGE = "Ollama is not on PATH. Install it from https://ollama.com and retry."

INSTRUCTION_RULES = [
    "You code one public policy into the Carbon Dioxide Removal (CDR) Policy Database.",
    "Follow the codebook definitions. Code only the named policy, even if the source mentions other measures.",
    "Use only the source text. If a category, year, amount, unit, or funding figure is not stated, return an empty string.",
    "Do not fill a field from outside knowledge of the country or from a typical policy of that title.",
    "Closed fields must use the allowed values. Where several values apply, join them with '; '.",
    "Use Multiple for Broad_method or Specific_method only when the source does not name particular methods.",
    "compliance_market_type, compliance_upper_bound, and compliance_upper_bound_unit apply only when the policy addresses use of CDR units in a compliance market. Otherwise leave them empty.",
    "Target fields apply only when the source states a quantitative target. Funding fields apply only when the source states an amount.",
    "CDR_link must be one sentence on why this document is relevant to carbon dioxide removal.",
    "Put genuine uncertainty in Comments. Do not restate the whole policy there.",
    "Return one JSON object and no other text. Every key below must be present. Unknown values are empty strings.",
]
CODEBOOK_RULES_HEADING = "Codebook rules:"
VARIABLES_HEADING = "Variables:"
JSON_KEYS_LABEL = "JSON keys:"
CLOSED_FIELD_NOTE = " Allowed values only: {values}."
OPEN_UNIT_NOTE = (
    " Prefer one of: {values}. "
    "If the source states a different unit, record that unit as written."
)
MULTI_VALUE_NOTE = " Multiple values are allowed, separated by '; '."
YEARS_AMENDED_NOTE = " List calendar years separated by '; ', or leave empty if the source states none."

USER_PROMPT_HEADER = (
    "Inventory context, already assigned. Code this instrument rather than restating these fields:"
)
USER_PROMPT_SOURCE_TYPE = "Source type:"
USER_PROMPT_SOURCE_TEXT = "Source text:"
USER_PROMPT_RETURN = "Return the JSON object now."
LABEL_JURISDICTION = "Jurisdiction"
LABEL_ISO = "ISO"
LABEL_DOCUMENT_TITLE = "Document title"
LABEL_YEAR_ENACTED = "Year enacted"
LABEL_URL = "URL"

SOURCE_LABEL_DOCUMENT = "full document text retrieved from the policy link"
SOURCE_LABEL_SUMMARY = (
    "policy summary from the inventory CDR relevance sentence. "
    "The full document was not used ({fallback_reason}). "
    "Code only what this summary supports."
)

NOTE_UNIT_OUTSIDE = "{field} uses '{piece}', which is outside the preferred unit list"
NOTE_VALUE_OUTSIDE = "{field} value '{piece}' is not in the codebook list"
NOTE_EXPECTED_SINGLE = "{field} was expected to be a single value"
OTHER_PREFIX = "Other: "
