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
    assert rag.build_context(text, 6000, estimate, rag.BM25Retriever()) == (text, {
        "summary": False, "introduction": False, "chunks_used": 0, "chunks_total": 0})


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
