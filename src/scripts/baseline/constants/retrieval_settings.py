"""Settings of the source retrieval and the keyword excerpt (``retrieval.py``)."""

import re

INPUT_POLICY_TEXT = "policy_text"
INPUT_WEBPAGE = "webpage_description"
INPUT_NO_TEXT = "no_text"
INPUT_SUMMARY = "expert_summary"
INPUT_TYPES = [INPUT_POLICY_TEXT, INPUT_WEBPAGE, INPUT_NO_TEXT, INPUT_SUMMARY]

OUTCOME_OK = "ok"
OUTCOME_EMPTY = "empty"
OUTCOME_ERROR = "error"
OUTCOME_TOO_LARGE = "too_large"

# Effectively "no limit": the first loop's PDF reader stops at this many tokens.
FULL_TEXT_TOKEN_LIMIT = 10_000_000
MIN_TEXT_TOKENS = 40
# An HTML page from a government site counts as policy text from this length on;
# shorter pages are usually landing or news pages that only describe the policy.
LONG_HTML_TOKENS = 1500
FETCH_ATTEMPTS = 2
FETCH_RETRY_SECONDS = 1.5
CACHE_ENCODING = "utf-8"

# Sites that host descriptions of policies (policy databases, factsheets) rather
# than the policy text. Their pages are webpage descriptions; if they link a PDF,
# the PDF is fetched instead because it is usually the policy itself.
DESCRIPTION_DOMAINS = (
    "climate-laws.org",
    "faolex.fao.org",
    "fao.org",
    "iea.org",
    "icapcarbonaction.com",
    "lse.ac.uk",
    "ecolex.org",
    "climatepolicydatabase.org",
)

# --------------------------------------------------------------- excerpt
# Keywords of the keyword excerpt (--context keyword, used for v1 and v2).
#
# Why this list: it names the CDR methods of the codebook (Broad_method /
# Specific_method), the carbon storage chain and the policy instruments
# (Instrument_type, compliance markets, targets, funding) in the main languages of
# the 20 jurisdictions. A chunk's score is simply how often these words occur.
#
# Known limitation (Sebastian's review): a passage that is relevant only through
# words that are not in this list (e.g. a funding table that never says "fund") can
# be left out. The excerpt limits this in two ways: the beginning of the document is
# always kept, and budget left after the keyword passages is filled with the text
# that follows the beginning. The targeted fix is the RAG context (--context rag),
# which searches per coding variable with the larger multilingual dictionary in
# keywords.json; the final benchmark compares both.
#
# The list is frozen on purpose: the v1 and v2 results in results/baseline were
# produced with exactly these words, and changing them would make those results
# irreproducible. Extend keywords.json (RAG) instead.
EXCERPT_KEYWORDS = [
    # carbon dioxide removal and sinks
    "carbon dioxide removal", "removal", "removals", "negative emission", "sequestration", "sequester",
    "carbon sink", "sinks", "net zero", "net-zero", "carbon neutral", "climate neutral",
    "afforestation", "reforestation", "forest", "peat", "wetland", "soil carbon", "agroforestry",
    "biochar", "bioenergy", "beccs", "direct air capture", "daccs", "enhanced weathering", "ocean",
    "carbon capture", "ccs", "ccus", "storage", "geological", "co2", "co₂", "lulucf",
    # policy instruments
    "target", "credit", "offset", "emissions trading", "ets", "market", "tax", "subsidy", "grant",
    "fund", "funding", "procurement", "purchase", "contract", "loan", "permit", "liability",
    "monitoring", "reporting", "verification", "mrv", "standard", "certification",
    # other languages
    "forêt", "puits", "séquestration", "stockage", "captage", "carbone",
    "bosque", "sumidero", "captura", "almacenamiento", "carbono", "remoción", "absorción",
    "floresta", "sumidouro", "armazenamento", "remoção",
    "wald", "senke", "speicherung", "abscheidung", "kohlenstoff", "entnahme", "negativemission",
    "foresta", "assorbimento", "stoccaggio", "cattura",
    "hutan", "penyerapan", "karbon",
    "лес", "поглощ", "углерод",
    "森林", "吸収", "炭素", "貯留", "回収",
    "碳汇", "固碳", "碳", "封存", "林",
    "산림", "흡수", "탄소", "저장",
]

PARAGRAPH_SPLIT = re.compile(r"\n+")
# Excerpt chunks are smaller than RAG chunks (350): the excerpt ranks by raw keyword
# counts, and smaller chunks keep one keyword-dense paragraph from pulling in a lot
# of unrelated text around it.
CHUNK_TOKENS = 250
# The beginning (title, purpose, scope) is always kept, up to a third of the budget.
LEAD_TOKENS = 1000
LEAD_MAX_SHARE = 3              # lead budget = min(LEAD_TOKENS, budget // LEAD_MAX_SHARE)
GAP = "[...]"
