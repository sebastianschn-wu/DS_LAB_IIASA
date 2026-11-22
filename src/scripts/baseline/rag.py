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
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

SUMMARY_MAX_TOKENS = 2500
SUMMARY_MIN_TOKENS = 80
LEAD_TOKENS = 600
CHUNK_TOKENS = 350
EMBED_BATCH = 32
EMBED_TIMEOUT = 300
GAP = "[...]"

# One query per coding question (fields of the codebook), in English.
QUERIES = {
    "scope": "Purpose and scope of this policy: does it set an overall framework, strategy or long-term target, "
             "or does it create one specific instrument such as a programme, scheme, tax or regulation?",
    "methods": "Which carbon dioxide removal methods are covered: afforestation, reforestation, forest management, "
               "soil carbon, wetlands, biochar, bioenergy with carbon capture and storage (BECCS), direct air "
               "capture (DACCS), enhanced weathering, ocean-based removal?",
    "storage": "Carbon capture, transport and geological storage of CO2, storage permits, liability and monitoring.",
    "instrument": "Instruments the policy establishes: grants, subsidies, tax credits, loans, funds, public "
                  "procurement, carbon credits, offsets, emissions trading, standards, certification, monitoring "
                  "reporting and verification (MRV), information or research funding.",
    "demand": "Who buys or pays for carbon removals: compliance carbon market, emissions trading system, crediting "
              "mechanism, government purchase of removals, contracts for difference.",
    "targets": "Quantified targets: net zero, emissions reduction, carbon removal or sink targets, target year, "
               "whether the target is legally binding.",
    "funding": "Budget, funding amount, financial support and money allocated to the programme.",
}

SUMMARY_HEADINGS = [
    "executive summary", "summary", "abstract", "overview", "synopsis", "key messages", "highlights",
    "summary for policymakers", "résumé", "resume", "synthèse", "resumen ejecutivo", "resumen", "sumário executivo",
    "sumário", "resumo", "zusammenfassung", "kurzfassung", "überblick", "sintesi", "riassunto", "ringkasan",
    "ikhtisar", "краткое содержание", "резюме", "概要", "要旨", "摘要", "概述", "要点", "요약", "개요",
]
# Used when there is no summary: the introduction usually says what the document does.
INTRO_HEADINGS = [
    "introduction", "introducción", "introdução", "introduzione", "einleitung", "einführung", "pendahuluan",
    "введение", "はじめに", "序言", "引言", "前言", "서론", "background and purpose",
]
INTRO_MAX_TOKENS = 1500
HEADING_MAX_CHARS = 120
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
    """Keyword retrieval (no model needed)."""

    name = "bm25"

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b

    def rank(self, chunks: list[str], queries: list[str]) -> list[list[int]]:
        docs = [_tokens(c) for c in chunks]
        frequencies = [Counter(d) for d in docs]
        lengths = [len(d) or 1 for d in docs]
        average = sum(lengths) / len(lengths)
        document_frequency = Counter(term for d in docs for term in set(d))
        n = len(docs)
        rankings = []
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
            rankings.append(sorted(range(n), key=lambda i: (-scores[i], i)))
        return rankings


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
        chunk_vectors = self.embed(chunks)
        query_vectors = self.embed(queries)

        def normalise(vector):
            length = math.sqrt(sum(v * v for v in vector)) or 1.0
            return [v / length for v in vector]

        chunk_vectors = [normalise(v) for v in chunk_vectors]
        rankings = []
        for query in query_vectors:
            q = normalise(query)
            scores = [sum(a * b for a, b in zip(q, c)) for c in chunk_vectors]
            rankings.append(sorted(range(len(chunks)), key=lambda i: (-scores[i], i)))
        return rankings


# ------------------------------------------------------------------ assemble
def build_context(text: str, budget: int, estimate, retriever) -> tuple[str, dict]:
    """Context of at most ``budget`` tokens: summary section + beginning + retrieved passages.

    Returns the context and a small report (summary found, chunks used/total).
    """
    if estimate(text) <= budget:
        return text, {"summary": False, "introduction": False, "chunks_used": 0, "chunks_total": 0}

    summary = find_summary(text, estimate, min(SUMMARY_MAX_TOKENS, budget // 2))
    section = "summary"
    if not summary:
        summary = find_summary(text, estimate, min(INTRO_MAX_TOKENS, budget // 3), INTRO_HEADINGS)
        section = "introduction"
    used = estimate(summary) if summary else 0
    chunks = chunk(text, estimate)
    chosen: set[int] = set()

    # Beginning of the document (title, purpose, scope).
    lead_budget = min(LEAD_TOKENS, max(0, budget - used) // 3)
    lead_used = 0
    for index, part in enumerate(chunks):
        size = estimate(part)
        if lead_used + size > lead_budget:
            break
        chosen.add(index)
        lead_used += size
    used += lead_used

    # Retrieved passages, taking turns between the questions.
    rankings = retriever.rank(chunks, list(QUERIES.values())) if chunks else []
    positions = [0] * len(rankings)
    progress = True
    while progress and rankings:
        progress = False
        for q, ranking in enumerate(rankings):
            while positions[q] < len(ranking) and ranking[positions[q]] in chosen:
                positions[q] += 1
            if positions[q] >= len(ranking):
                continue
            index = ranking[positions[q]]
            positions[q] += 1
            size = estimate(chunks[index])
            if used + size > budget:
                continue
            chosen.add(index)
            used += size
            progress = True

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
              "chunks_used": len(chosen), "chunks_total": len(chunks)}
    return "\n".join(parts), report
