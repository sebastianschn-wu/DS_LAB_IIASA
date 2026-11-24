"""Keyword lists for the RAG keyword retriever, built from the multilingual dictionary.

The translations live in ``keywords.json`` (one entry per concept, one list per
language). This module only decides which concepts belong to which coding
variable, so a new language or a new synonym is added in one place and reaches
every variable that uses the concept.

Why a reviewed dictionary and not a translation library at run time: libraries
such as ``deep-translator`` call Google Translate over the internet, so a run would
need network access and could change from one day to the next (not
reproducible). They also translate whole words, while the search terms are often
stems ("subsid", "financ") or abbreviations (CCS, MRV, LULUCF) that come back
unchanged or wrong. A translation library can still be used once, offline from the
pipeline, to suggest terms for a new language; the suggestions are then checked
and added to ``keywords.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

KEYWORDS_FILE = Path(__file__).resolve().with_name("keywords.json")

# Languages of the 20 jurisdictions in the policy sheet (official languages; India,
# South Africa, Australia, Canada, UK, US and the EU are covered by English/French).
LANGUAGES = ["en", "es", "pt", "fr", "de", "it", "id", "ru", "ja", "zh", "ko", "tr", "ar"]

# Concepts per coding question (key of QUERIES in rag_settings) and the codebook
# variables each question serves.
VARIABLE_CONCEPTS = {
    # Policy_scope
    "scope": ["purpose", "act_reference", "scope_framework"],
    # Broad_method, Specific_method
    "methods": ["afforestation", "reforestation", "agroforestry", "forest", "soil_carbon", "wetland", "peat",
                "blue_carbon", "biochar", "bioenergy", "direct_air_capture", "enhanced_weathering",
                "carbon_removal", "carbon_sink", "land_use"],
    # Specific_method (BECCS/DACCS storage side), Value_chain_focus (storage)
    "storage": ["carbon_capture", "geological_storage", "co2_transport"],
    # Instrument_broad, Instrument_type
    "instrument": ["grant_subsidy", "tax_incentive", "loan_guarantee", "fund", "procurement_auction",
                   "standard_certification", "permit_obligation", "research_programme"],
    # Value_chain_focus (demand), compliance_market_type, compliance_upper_bound(_unit)
    "demand": ["carbon_credit", "emissions_trading", "carbon_market", "purchase"],
    # Target_type, Target_binding, Target_year, Target_amount, Target_unit
    "targets": ["target", "net_zero", "emission_reduction", "binding"],
    # Funding_sum, Funding_unit
    "funding": ["budget", "funding_finance"],
}

# Language-independent patterns ("re:" marks a regular expression).
PATTERNS = {
    "targets": [r"re:\b20[2-6]\d\b", r"re:\d+(\.\d+)?\s?%", r"re:\b(mt|gt|kt)\s?co2",
                r"re:(million|billion) (tonnes|tons)"],
    "funding": [r"re:(€|\$|£|eur|usd|gbp|aud|cad|inr|rmb|brl|jpy|krw|try|sar|idr|rub|zar|mxn|ars)\s?\d",
                r"re:\d+([.,]\d+)?\s?(million|billion|mio|mrd|bn|crore|lakh)"],
}

# Concept for the climate/carbon context check (see NEEDS_CONTEXT in rag_settings).
CONTEXT_CONCEPT = "climate_context"


def load_dictionary(path: Path = KEYWORDS_FILE) -> dict[str, dict[str, list[str]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {name: entry for name, entry in data.items() if not name.startswith("_")}


DICTIONARY = load_dictionary()


def terms(*concepts: str, dictionary: dict[str, dict[str, list[str]]] = DICTIONARY) -> list[str]:
    """All search terms of the concepts in every language, lower-cased, without duplicates."""
    seen: dict[str, None] = {}
    for concept in concepts:
        for language_terms in dictionary[concept].values():
            for term in language_terms:
                seen.setdefault(term.casefold(), None)
    return list(seen)


KEYWORDS = {variable: terms(*concepts) + PATTERNS.get(variable, [])
            for variable, concepts in VARIABLE_CONCEPTS.items()}
CONTEXT_TERMS = terms(CONTEXT_CONCEPT)
