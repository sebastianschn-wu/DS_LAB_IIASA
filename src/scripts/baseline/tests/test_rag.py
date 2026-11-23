"""RAG context: summary detection, retrieval, budget (no model needed)."""

import rag


def estimate(text: str) -> int:
    return (len(text) + 3) // 4


FILLER = "The ministry shall publish administrative notices about office organisation and staff matters. "


def long_document(with_summary=True):
    parts = ["NATIONAL LONG-TERM STRATEGY", "Contents", "1. Executive Summary 3", "2. Background 5"]
    if with_summary:
        parts += ["1. Executive Summary",
                  "This strategy sets a net zero target for 2050 and expands forest carbon sinks. " * 12]
    parts += ["2. Background"] + [FILLER * 4 for _ in range(80)]
    parts += ["The government will purchase carbon removal credits through public procurement contracts "
              "for direct air capture and BECCS. " * 3]
    parts += [FILLER * 4 for _ in range(80)]
    return "\n".join(parts)


def test_find_summary_skips_table_of_contents():
    summary = rag.find_summary(long_document(), estimate)
    assert summary.startswith("This strategy sets a net zero target")
    assert "Background" not in summary


def test_no_summary_when_absent():
    assert rag.find_summary(long_document(with_summary=False), estimate) == ""


def test_short_text_is_returned_whole():
    text = "Short act about forests."
    context, report = rag.build_context(text, 6000, estimate, rag.BM25Retriever())
    assert context == text and report["chunks_used"] == 0


def test_context_has_summary_retrieved_passage_and_fits_budget():
    context, report = rag.build_context(long_document(), 1500, estimate, rag.BM25Retriever())
    assert estimate(context) <= 1500 + 30  # small allowance for the section labels
    assert report["summary"] and report["chunks_used"] < report["chunks_total"]
    assert context.startswith("[Summary section of the document]")
    assert "public procurement contracts" in context
    assert rag.GAP in context


def test_bm25_handles_cjk():
    chunks = ["行政事務に関する規定", "森林による二酸化炭素の吸収を促進する", "職員の配置"]
    ranking = rag.BM25Retriever().rank(chunks, ["森林 吸収"])[0]
    assert ranking[0] == 1


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class FakeRequests:
    """Embeds a text as counts of a few keywords, so similarity is predictable."""

    calls = 0
    WORDS = ["forest", "procurement", "office", "target"]

    def post(self, url, json, timeout):
        FakeRequests.calls += 1
        return FakeResponse({"embeddings": [[t.lower().count(w) + 0.01 for w in self.WORDS] for t in json["input"]]})


def test_embed_retriever_ranks_and_caches(tmp_path):
    retriever = rag.OllamaEmbedRetriever(FakeRequests(), "http://x", "fake", tmp_path)
    chunks = ["office office office", "forest forest", "procurement of removals"]
    first = retriever.rank(chunks, ["forest carbon"])[0]
    calls = FakeRequests.calls
    second = retriever.rank(chunks, ["forest carbon"])[0]
    assert first[0] == 1 and first == second
    assert FakeRequests.calls == calls  # second time from the cache


def test_noise_filter():
    toc = "\n".join(f"{i}. Chapter title number {i} ........................ {i * 3}" for i in range(1, 9))
    nav = "Home\nNews stories, speeches\nGuidance\nCopyright notice\nCookie settings\nPrivacy\nSign in\nMenu"
    garbled = "/heenmedial/behmedial /adiolated/tehmedial/khahmedial/tehmedial /nooniolated/aleffinal/jeemmedial/"
    text = "The Act establishes a fund for forest restoration and pays landholders per tonne of carbon removed."
    assert rag.is_noise(toc) and rag.is_noise(nav) and rag.is_noise(garbled)
    assert not rag.is_noise(text)


def test_questions_are_gated_by_topic():
    forest_plan = "This plan restores forest and peat land and increases the carbon sink. " * 5
    assert "storage" not in rag.active_queries(forest_plan)
    assert "methods" in rag.active_queries(forest_plan)
    assert "scope" in rag.active_queries(forest_plan)


def test_noise_is_never_sent():
    toc = "\n".join(f"{i}. Storage of carbon dioxide ............ {i}" for i in range(1, 12))
    document = "\n".join(["NATIONAL STRATEGY", toc] + [FILLER * 4 for _ in range(60)])
    context, report = rag.build_context(document, 1500, estimate, rag.BM25Retriever())
    assert "............" not in context
    assert report["noise_chunks"] >= 1


def test_legal_table_of_contents_is_noise_but_legal_text_is_not():
    toc = "\n".join(f"Sec. {11100 + i}. Program number {i} for highways." for i in range(12))
    body = ("Sec. 40305. Carbon storage validation and testing.\n"
            "(a) In General.--The Secretary shall establish a program to provide\n"
            "grants for the construction of commercial-scale carbon storage\n"
            "projects, including geological storage sites, and shall make\n"
            "awards on a competitive basis to eligible entities.\n")
    assert rag.is_noise(toc)
    assert not rag.is_noise(body)


def test_keyword_retriever_finds_passages_per_variable():
    chunks = ["The Commonwealth will purchase carbon credits through a reverse auction.",
              "The plan aims to reach net zero by 2050 and cut emissions 43% by 2030.",
              "Office hours of the ministry and staff matters.",
              "A budget of AUD 4.5 billion is allocated to the carbon farming fund."]
    retriever = rag.KeywordRetriever()
    scores = retriever.scores(chunks, [rag.QUERIES["demand"], rag.QUERIES["targets"], rag.QUERIES["funding"]])
    assert max(range(4), key=lambda i: scores[0][i]) == 0
    assert max(range(4), key=lambda i: scores[1][i]) == 1
    assert max(range(4), key=lambda i: scores[2][i]) == 3
    assert all(row[2] == 0 for row in scores)


def test_generic_words_need_carbon_context():
    retriever = rag.KeywordRetriever()
    toll = "States may sell toll credits through competitive procurement for highway projects."
    carbon = "The Secretary shall purchase carbon removal credits through competitive procurement."
    assert retriever.score_chunk(toll, "demand") == 0
    assert retriever.score_chunk(carbon, "demand") > 0
