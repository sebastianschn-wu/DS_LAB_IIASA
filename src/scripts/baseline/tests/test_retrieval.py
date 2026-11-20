"""Input-type classification and excerpting (no network)."""

import retrieval


def estimate(text: str) -> int:
    return (len(text) + 3) // 4


def fetched(outcome="ok", text="x" * 400, tokens=100, is_pdf=False, final_url="", followed=False, error=""):
    return retrieval.result(outcome, text, tokens, is_pdf, final_url, followed, error)


def test_no_text_when_fetch_failed():
    kind, reason = retrieval.classify(fetched("error", "", 0, error="HTTPError: 404"), "https://gov.example/x")
    assert kind == retrieval.INPUT_NO_TEXT
    assert "404" in reason


def test_pdf_is_policy_text():
    kind, _ = retrieval.classify(fetched(is_pdf=True), "https://gov.example/law.pdf")
    assert kind == retrieval.INPUT_POLICY_TEXT


def test_database_page_is_description():
    kind, _ = retrieval.classify(fetched(tokens=5000, final_url="https://www.climate-laws.org/document/abc"),
                                 "https://www.climate-laws.org/document/abc")
    assert kind == retrieval.INPUT_WEBPAGE


def test_long_government_page_is_policy_text_short_is_description():
    long_page = fetched(tokens=retrieval.LONG_HTML_TOKENS + 1, final_url="https://www.legislation.gov.uk/x")
    short_page = fetched(tokens=300, final_url="https://www.gov.uk/news/x")
    assert retrieval.classify(long_page, "")[0] == retrieval.INPUT_POLICY_TEXT
    assert retrieval.classify(short_page, "")[0] == retrieval.INPUT_WEBPAGE


def test_subdomain_matches_description_domain():
    assert retrieval.is_description_domain("https://faolex.fao.org/docs/pdf/x.pdf")
    assert not retrieval.is_description_domain("https://www.gov.uk/x")


def test_excerpt_keeps_short_text_unchanged():
    text = "Short policy text about forests."
    assert retrieval.excerpt(text, 6000, estimate) == (text, False)


def test_excerpt_respects_budget_keeps_beginning_and_relevant_passages():
    intro = "Title of the act. Purpose and scope of this act."
    filler = ["Administrative provisions on office hours and staff number %d. " % i * 6 for i in range(60)]
    relevant = "The act sets a target for carbon dioxide removal and funds afforestation and biochar. " * 4
    text = "\n".join([intro] + filler[:30] + [relevant] + filler[30:])
    short, shortened = retrieval.excerpt(text, 600, estimate)
    assert shortened
    assert estimate(short) <= 650
    assert short.startswith("Title of the act")
    assert "carbon dioxide removal" in short
    assert "[...]" in short


def test_overrides(tmp_path):
    path = tmp_path / "overrides.csv"
    path.write_text("sheet_row,input_type,note\n12,webpage_description,checked by hand\n", encoding="utf-8")
    assert retrieval.read_overrides(path) == {"12": "webpage_description"}
    assert retrieval.read_overrides(tmp_path / "missing.csv") == {}
