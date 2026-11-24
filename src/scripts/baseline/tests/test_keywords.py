"""Multilingual keyword dictionary (constants/keywords.json)."""

from constants import keywords
from constants.rag_settings import NEEDS_CONTEXT, QUERIES


def test_every_concept_covers_every_language():
    for concept, entry in keywords.DICTIONARY.items():
        missing = [lang for lang in keywords.LANGUAGES if not entry.get(lang)]
        assert not missing, f"{concept}: no terms for {missing}"
        unknown = set(entry) - set(keywords.LANGUAGES)
        assert not unknown, f"{concept}: unknown language codes {unknown}"


def test_terms_are_clean():
    for concept, entry in keywords.DICTIONARY.items():
        for lang, terms in entry.items():
            for term in terms:
                assert term.strip(), f"{concept}/{lang}: empty term"
                # One CJK character is a word (林 forest, 碳 carbon); other scripts need 2+ letters.
                if lang not in ("ja", "zh", "ko"):
                    assert len(term.strip()) >= 2, f"{concept}/{lang}: '{term}' is too short to search for"


def test_every_question_has_keywords_and_every_concept_is_used():
    assert set(keywords.VARIABLE_CONCEPTS) == set(QUERIES)
    assert NEEDS_CONTEXT <= set(QUERIES)
    used = {c for concepts in keywords.VARIABLE_CONCEPTS.values() for c in concepts} | {keywords.CONTEXT_CONCEPT}
    assert used == set(keywords.DICTIONARY), "concepts in keywords.json and keywords.py must match"


def test_keywords_are_lower_case_and_unique():
    for variable, terms in keywords.KEYWORDS.items():
        plain = [t for t in terms if not t.startswith("re:")]
        assert plain == [t.casefold() for t in plain]
        assert len(plain) == len(set(plain)), variable
