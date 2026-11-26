"""RAG context for documents that are longer than the token budget.

Instead of cutting a long PDF or sending the expert summary, the model gets a
context of at most ``budget`` tokens built in three steps:

1. Summary section: if the document has its own summary (Executive summary,
   Summary, Abstract, Overview, Zusammenfassung, Resumen, 概要, 摘要, ...), it
   goes first, up to ``SUMMARY_MAX_TOKENS``. Without one, the introduction is
   used (up to ``INTRO_MAX_TOKENS``).
2. Beginning: title, purpose and scope (first ``LEAD_TOKENS`` tokens).
3. Retrieved passages: the document is split into chunks of about
   ``CHUNK_TOKENS`` tokens; for every coding question of the codebook
   (``QUERIES``) the most similar chunks are retrieved, taking turns between the
   questions so each field gets evidence, until the budget is full.

Retrieval uses embeddings from Ollama (default ``bge-m3``, multilingual, so the
English questions also find passages in German, Spanish, Japanese, ...) and
caches them on disk. ``bm25`` is a keyword alternative that needs no model.

Version 2 (after inspecting what version 1 sent to the model, see
``results/baseline/rag_inspection.md``):

* Noise filter: table-of-contents chunks, website navigation / copyright
  boilerplate and garbled PDF text are never sent.
* (Version 2 only: questions were skipped when their keywords hardly occurred in
  the document. Removed in version 3, see ``active_queries``.)
* No fixed quota per question: chunks are ranked by how unusually similar they are
  to a question within this document (z-score), only clearly relevant ones
  (z >= ``MIN_Z``) are taken, and one question fills at most ``QUERY_CAP`` of the
  retrieval budget.
* About ``FRAME_SHARE`` of the budget goes to the document's summary/introduction
  and beginning, so the model still sees what kind of document it is; budget that
  relevant passages do not fill also goes to the beginning.

Version 3: every question is asked for every document (no keyword gates), and the
keyword retriever uses the multilingual dictionary in ``constants/keywords.json``.
All numeric settings, with the reasoning and references behind them, are in
``constants/rag_settings.py``.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

from constants.keywords import CONTEXT_TERMS, KEYWORDS
from constants.rag_settings import (
    BM25_B,
    BM25_K1,
    BOILERPLATE,
    BOILERPLATE_MIN_HITS,
    CHUNK_TOKENS,
    DEFAULT_EMBED_MODEL,  # noqa: F401  (used by baseline.script.py)
    EMBED_BATCH,
    EMBED_TIMEOUT,
    FRAME_SHARE,
    GAP,
    GLYPH_NAMES_MIN_HITS,
    HEADING_MAX_CHARS,
    INTRO_HEADINGS,
    INTRO_MAX_TOKENS,
    LEAD_TOKENS,
    MENU_MIN_LINES,
    MENU_SHORT_LINE_SHARE,
    MENU_SHORT_LINE_WORDS,
    MIN_LETTER_SHARE,
    MIN_Z,
    NEEDS_CONTEXT,
    QUERIES,
    QUERY_CAP,
    QUERY_CAP_MIN_CHUNKS,
    RAG_VERSION,  # noqa: F401  (used as rag.RAG_VERSION by baseline.script.py)
    SUMMARY_HEADINGS,
    SUMMARY_MAX_TOKENS,
    SUMMARY_MIN_TOKENS,
    TOC_LINE_SHARE,
    TOC_MIN_LINES,
)

_TOC_LINE = re.compile(r"(\.{4,}|…{2,}|(\s\.){3,})\s*\d*\s*$|^\s*[A-Z0-9][^.;:]{15,90}\s\d{1,3}\s*$")
# Heading-only lines of a legal table of contents ("Sec. 11101. Authorization of appropriations.").
_LEGAL_HEADING = re.compile(r"^\s*(sec\.|section|article|art\.|chapter|part|title|subtitle|division)\s*"
                            r"[\dIVXLC]+[\w\-—.:]*\s.{0,90}$", re.IGNORECASE)
_GLYPH_NAMES = re.compile(r"(medial|iolated|initial|final)/", re.IGNORECASE)


def is_noise(text: str) -> bool:
    """Table of contents, website navigation/boilerplate or garbled PDF text."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if not lines:
        return True
    if len(_GLYPH_NAMES.findall(text)) >= GLYPH_NAMES_MIN_HITS:
        return True
    letters = sum(ch.isalpha() for ch in text)
    if letters < MIN_LETTER_SHARE * len(text.replace(" ", "")):
        return True
    toc = sum(bool(_TOC_LINE.search(line) or _LEGAL_HEADING.match(line)) for line in lines)
    if len(lines) >= TOC_MIN_LINES and toc >= TOC_LINE_SHARE * len(lines):
        return True
    lowered = text.casefold()
    boilerplate = sum(lowered.count(word) for word in BOILERPLATE)
    if boilerplate >= BOILERPLATE_MIN_HITS:
        return True
    # Navigation menus: mostly very short lines plus at least one boilerplate word
    # (legal text split into short lines, e.g. "(", "paragraph 3", ")", has none).
    short = sum(len(line.split()) <= MENU_SHORT_LINE_WORDS for line in lines)
    return len(lines) >= MENU_MIN_LINES and short >= MENU_SHORT_LINE_SHARE * len(lines) and boilerplate >= 1


def active_queries(text: str) -> list[str]:
    """Question names to ask for this document: all of them since RAG version 3.

    Version 2 skipped some questions (methods, storage, demand, funding) when their
    keywords occurred fewer than 5 times in the document. All of these serve
    variables the codebook codes for every policy (Funding_sum, Value_chain_focus,
    Specific_method, ...), and a funding amount that is mentioned only once or twice
    is exactly what we must not miss. A question the document does not address still
    gets no passages, because chunks need a positive score and z >= MIN_Z.
    ``text`` is kept as a parameter so the report format stays the same.
    """
    return list(QUERIES)


_CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯]")
_WORD = re.compile(r"[^\W\d_]{2,}", re.UNICODE)


# ---------------------------------------------------------------- chunking
def chunk(text: str, estimate, size: int = CHUNK_TOKENS) -> list[str]:
    """Split into chunks of about ``size`` tokens along paragraph boundaries."""
    pieces: list[str] = []
    for paragraph in re.split(r"\n+", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        while estimate(paragraph) > size * 2:
            cut = max(1, len(paragraph) * size // max(1, estimate(paragraph)))
            pieces.append(paragraph[:cut])
            paragraph = paragraph[cut:]
        pieces.append(paragraph)
    chunks, current, used = [], [], 0
    for piece in pieces:
        tokens = estimate(piece) + 1
        if current and used + tokens > size:
            chunks.append("\n".join(current))
            current, used = [], 0
        current.append(piece)
        used += tokens
    if current:
        chunks.append("\n".join(current))
    return chunks


# ------------------------------------------------------------ summary section
def _heading_match(line: str, headings: list[str]) -> bool:
    """True if a short line ends with one of the headings.

    PDF text often glues page numbers or running headers to a heading
    ("Page 1Executive Summary", "1EXECUTIVE SUMMARY"), so the heading only has to
    end the line. Table-of-contents lines end with a page number or dots and do
    not match.
    """
    stripped = line.strip().rstrip(":").strip()
    if not stripped or len(stripped) > HEADING_MAX_CHARS:
        return False
    lowered = stripped.casefold()
    for heading in sorted(headings, key=len, reverse=True):
        if lowered.endswith(heading):
            first = stripped[-len(heading)]
            if first.isalpha() and first.islower() and first.upper() != first:
                continue  # "... we give a summary": a sentence, not a heading
            before = lowered[: -len(heading)]
            # "...asumidos.Resumen", "2050EXECUTIVE SUMMARY" and "1. Summary" are fine;
            # a longer word ending in the heading ("presummary") is not.
            if not before or not before[-1].isalpha() or before[-1] in ".":
                return True
            if stripped[-len(heading)].isupper() and before[-1].islower():
                return True  # glued: "ejecutivoIntroducción"
    return False


def _looks_like_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 80 or stripped.endswith((".", ",", ";")):
        return False
    numbered = re.match(r"^(\d+(\.\d+)*\.?|[ivxIVX]+\.|chapter\s+\d+)\s+\S", stripped, re.IGNORECASE)
    upper = stripped.isupper() and len(stripped) > 3
    return bool(numbered or upper)


def find_summary(text: str, estimate, max_tokens: int = SUMMARY_MAX_TOKENS,
                 headings: list[str] | None = None) -> str:
    """The document's own summary section, or '' if there is none.

    Takes the first heading line that names a summary (outside the table of
    contents, i.e. followed by real text) and the text up to the next heading,
    capped at ``max_tokens``. ``headings`` defaults to the summary headings.
    """
    headings = SUMMARY_HEADINGS if headings is None else headings
    lines = text.split("\n")
    for start, line in enumerate(lines):
        if not _heading_match(line, headings):
            continue
        body: list[str] = []
        used = 0
        for following in lines[start + 1:]:
            if body and used > SUMMARY_MIN_TOKENS and _looks_like_heading(following):
                break
            tokens = estimate(following) + 1
            if used + tokens > max_tokens:
                break
            body.append(following)
            used += tokens
        section = "\n".join(body).strip()
        # A table-of-contents entry has almost no text before the next heading.
        if estimate(section) >= SUMMARY_MIN_TOKENS:
            return section
    return ""


# ---------------------------------------------------------------- retrievers
def _tokens(text: str) -> list[str]:
    lowered = text.casefold()
    words = _WORD.findall(lowered)
    cjk = _CJK.findall(lowered)
    words += [a + b for a, b in zip(cjk, cjk[1:])]  # character bigrams for CJK text
    return words


class BM25Retriever:
    """Okapi BM25 keyword retrieval (no model needed), alternative to the default retriever.

    Standard probabilistic ranking function of information retrieval (Robertson &
    Zaragoza 2009; Manning et al. 2008, section 11.4.3), with the "+1" idf of Lucene
    so scores stay positive. ``k1`` sets how fast repeated terms saturate, ``b`` how
    strongly long chunks are penalised; see ``BM25_K1`` / ``BM25_B`` in
    ``constants/rag_settings.py`` for the chosen values and why.
    """

    name = "bm25"

    def __init__(self, k1: float = BM25_K1, b: float = BM25_B):
        self.k1, self.b = k1, b

    def rank(self, chunks: list[str], queries: list[str]) -> list[list[int]]:
        scores = self.scores(chunks, queries)
        return [sorted(range(len(chunks)), key=lambda i: (-row[i], i)) for row in scores]

    def scores(self, chunks: list[str], queries: list[str]) -> list[list[float]]:
        docs = [_tokens(c) for c in chunks]
        frequencies = [Counter(d) for d in docs]
        lengths = [len(d) or 1 for d in docs]
        average = sum(lengths) / len(lengths)
        document_frequency = Counter(term for d in docs for term in set(d))
        n = len(docs)
        all_scores = []
        for query in queries:
            terms = set(_tokens(query))
            scores = []
            for freq, length in zip(frequencies, lengths):
                score = 0.0
                for term in terms:
                    if term not in freq:
                        continue
                    idf = math.log(1 + (n - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5))
                    tf = freq[term]
                    score += idf * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * length / average))
                scores.append(score)
            all_scores.append(scores)
        return all_scores


def _keyword_matchers(words: list[str]):
    compiled = []
    for word in words:
        if word.startswith("re:"):
            compiled.append(re.compile(word[3:], re.IGNORECASE))
        else:
            compiled.append(word.casefold())
    return compiled


class KeywordRetriever:
    """Targeted keyword search per variable (default retriever, no model needed).

    A chunk's score for a variable is the sum of log(1 + hits) over that
    variable's keywords, so a passage that mentions several different keywords
    beats one that repeats a single word (the same sublinear term-frequency idea as
    BM25's saturation). Keywords come from the multilingual dictionary in
    ``constants/keywords.json``.
    """

    name = "keywords"

    def __init__(self):
        self.matchers = {name: _keyword_matchers(words) for name, words in KEYWORDS.items()}
        self.by_question = {question: name for name, question in QUERIES.items()}

    def score_chunk(self, text: str, name: str) -> float:
        lowered = text.casefold()
        total = 0.0
        for matcher in self.matchers.get(name, []):
            hits = len(matcher.findall(text)) if isinstance(matcher, re.Pattern) else lowered.count(matcher)
            if hits:
                total += math.log1p(hits)
        context = sum(lowered.count(term) for term in CONTEXT_TERMS)
        if name in NEEDS_CONTEXT and context == 0:
            return 0.0
        return total * (1 + math.log1p(context))

    def scores(self, chunks: list[str], queries: list[str]) -> list[list[float]]:
        return [[self.score_chunk(c, self.by_question.get(q, q)) for c in chunks] for q in queries]

    def rank(self, chunks: list[str], queries: list[str]) -> list[list[int]]:
        scores = self.scores(chunks, queries)
        return [sorted(range(len(chunks)), key=lambda i: (-row[i], i)) for row in scores]


class OllamaEmbedRetriever:
    """Embedding retrieval with an Ollama embedding model, cached per chunk text."""

    name = "embed"

    def __init__(self, requests_module, host: str, model: str, cache_dir: Path):
        self.requests = requests_module
        self.host = host.rstrip("/")
        self.model = model
        self.cache_dir = cache_dir

    def _cache_path(self, texts: list[str]) -> Path:
        digest = hashlib.sha256((self.model + "\x00" + "\x00".join(texts)).encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def embed(self, texts: list[str]) -> list[list[float]]:
        path = self._cache_path(texts)
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
        vectors: list[list[float]] = []
        for start in range(0, len(texts), EMBED_BATCH):
            batch = texts[start:start + EMBED_BATCH]
            response = self.requests.post(f"{self.host}/api/embed", json={"model": self.model, "input": batch},
                                          timeout=EMBED_TIMEOUT)
            response.raise_for_status()
            vectors.extend(response.json()["embeddings"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(vectors), encoding="utf-8")
        return vectors

    def check(self) -> None:
        """Fail early with a clear message if the embedding model is missing."""
        try:
            self.embed(["test"])
        except Exception as exc:
            raise SystemExit(f"Embedding model '{self.model}' is not available in Ollama ({exc}). "
                             f"Install it with: ollama pull {self.model}  (or use --retriever bm25)")

    def rank(self, chunks: list[str], queries: list[str]) -> list[list[int]]:
        scores = self.scores(chunks, queries)
        return [sorted(range(len(chunks)), key=lambda i: (-row[i], i)) for row in scores]

    def scores(self, chunks: list[str], queries: list[str]) -> list[list[float]]:
        chunk_vectors = self.embed(chunks)
        query_vectors = self.embed(queries)

        def normalise(vector):
            length = math.sqrt(sum(v * v for v in vector)) or 1.0
            return [v / length for v in vector]

        chunk_vectors = [normalise(v) for v in chunk_vectors]
        return [[sum(a * b for a, b in zip(normalise(q), c)) for c in chunk_vectors] for q in query_vectors]


# ------------------------------------------------------------------ assemble
def _zscores(row: list[float]) -> list[float]:
    n = len(row)
    mean = sum(row) / n
    std = math.sqrt(sum((x - mean) ** 2 for x in row) / n) or 1.0
    return [(x - mean) / std for x in row]


def build_context(text: str, budget: int, estimate, retriever) -> tuple[str, dict]:
    """Context of at most ``budget`` tokens: summary/introduction + beginning + relevant passages.

    Returns the context and a report (what was found, how many chunks, which
    questions were asked and how many tokens each contributed).
    """
    empty = {"summary": False, "introduction": False, "chunks_used": 0, "chunks_total": 0,
             "noise_chunks": 0, "questions": [], "tokens_by_source": {}}
    if estimate(text) <= budget:
        return text, empty

    frame_budget = int(budget * FRAME_SHARE)
    summary = find_summary(text, estimate, min(SUMMARY_MAX_TOKENS, frame_budget))
    section = "summary"
    if not summary:
        summary = find_summary(text, estimate, min(INTRO_MAX_TOKENS, frame_budget), INTRO_HEADINGS)
        section = "introduction"
    used = estimate(summary) if summary else 0
    by_source = {section: used} if summary else {}

    chunks = chunk(text, estimate)
    noise = [is_noise(c) for c in chunks]
    chosen: dict[int, str] = {}

    def add_beginning(limit: int) -> None:
        nonlocal used
        for index, part in enumerate(chunks):
            if used >= limit:
                break
            if index in chosen or noise[index]:
                continue
            size = estimate(part)
            if used + size > limit:
                break
            chosen[index] = "beginning"
            used += size
            by_source["beginning"] = by_source.get("beginning", 0) + size

    add_beginning(max(frame_budget, used + LEAD_TOKENS))

    # Relevant passages: unusually similar to an asked question, no fixed quota.
    names = active_queries(text)
    candidates = []
    if names and chunks:
        all_scores = retriever.scores(chunks, list(QUERIES.values()))  # all questions: one cached embedding call
        order = list(QUERIES)
        for name in names:
            row = all_scores[order.index(name)]
            for index, z in enumerate(_zscores(row)):
                if z >= MIN_Z and row[index] > 0 and not noise[index]:
                    candidates.append((z, index, name))
    candidates.sort(key=lambda item: (-item[0], item[1]))
    cap = max(QUERY_CAP * (budget - used), CHUNK_TOKENS * QUERY_CAP_MIN_CHUNKS)
    per_question: dict[str, int] = {}
    for z, index, name in candidates:
        if index in chosen:
            continue
        size = estimate(chunks[index])
        if used + size > budget or per_question.get(name, 0) + size > cap:
            continue
        chosen[index] = name
        used += size
        per_question[name] = per_question.get(name, 0) + size
        by_source[name] = by_source.get(name, 0) + size

    # Budget left over: more of the beginning.
    add_beginning(budget)

    parts: list[str] = []
    if summary:
        label = "Summary section" if section == "summary" else "Introduction"
        parts += [f"[{label} of the document]", summary, "[Passages from the document]"]
    previous = -1
    for index in sorted(chosen):
        if previous >= 0 and index != previous + 1:
            parts.append(GAP)
        parts.append(chunks[index])
        previous = index
    report = {"summary": bool(summary) and section == "summary",
              "introduction": bool(summary) and section == "introduction",
              "chunks_used": len(chosen), "chunks_total": len(chunks), "noise_chunks": sum(noise),
              "questions": names, "tokens_by_source": by_source}
    return "\n".join(parts), report
