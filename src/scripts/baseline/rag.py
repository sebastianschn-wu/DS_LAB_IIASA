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
* Questions only count when the document is about them: a question is skipped if
  its keywords hardly occur in the document (no storage passages for a forest
  plan, no market passages for a strategy without markets).
* No fixed quota per question: chunks are ranked by how unusually similar they are
  to a question within this document (z-score), only clearly relevant ones
  (z >= ``MIN_Z``) are taken, and one question fills at most ``QUERY_CAP`` of the
  retrieval budget.
* About ``FRAME_SHARE`` of the budget goes to the document's summary/introduction
  and beginning, so the model still sees what kind of document it is; budget that
  relevant passages do not fill also goes to the beginning.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

RAG_VERSION = 2
SUMMARY_MAX_TOKENS = 1800
SUMMARY_MIN_TOKENS = 80
LEAD_TOKENS = 600           # minimum for the beginning of the document
FRAME_SHARE = 0.3           # share of the budget for summary/introduction + beginning
MIN_Z = 1.0                 # a chunk must be this many standard deviations above the document mean
QUERY_CAP = 0.3             # one question fills at most this share of the retrieval budget
GATE_MIN_HITS = 5           # keyword hits a document needs before a gated question is asked
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

# Keywords per coding variable (Sebastian's idea): passages where the answer for a
# variable is likely to be. "re:" marks a regular expression. Several languages.
#   scope      -> Policy_scope              methods  -> Broad_method, Specific_method
#   storage    -> Specific_method (CO2)     instrument -> Instrument_broad, Instrument_type
#   demand     -> Value_chain_focus, compliance_market_type
#   targets    -> Target_type, Target_binding, Target_value/unit/year
#   funding    -> Funding
KEYWORDS = {
    "scope": ["purpose", "objective", "aims to", "the aim", "this act", "this regulation", "this directive",
              "this strategy", "this plan", "this programme", "this program", "shall apply", "scope",
              "establishes", "framework", "vision", "objet", "objetivo", "objeto", "finalidad", "zweck",
              "目的", "目标", "цель", "tujuan", "목적"],
    "methods": ["afforestation", "reforestation", "agroforestry", "forest", "soil carbon", "soil organic",
                "wetland", "peat", "mangrove", "seagrass", "blue carbon", "biochar", "bioenergy", "beccs",
                "direct air capture", "daccs", "enhanced weathering", "ocean alkalin", "carbon removal",
                "removals", "negative emission", "carbon sink", "lulucf", "land use", "sequestration",
                "bosque", "forestación", "reforestación", "sumidero", "forêt", "boisement", "puits de carbone",
                "floresta", "reflorestamento", "wald", "aufforstung", "senke", "森林", "植林", "吸収源", "碳汇",
                "造林", "лес", "hutan", "산림"],
    "storage": ["carbon capture", "ccs", "ccus", "geological storage", "storage site", "co2 storage",
                "storage of carbon dioxide", "injection", "co2 transport", "pipeline", "storage permit", "leakage",
                "captage", "stockage géologique", "captura de carbono", "almacenamiento geológico",
                "armazenamento", "abscheidung", "speicherung", "貯留", "封存", "捕集", "хранени", "저장"],
    "instrument": ["grant", "subsid", "tax credit", "tax incentive", "tax relief", "loan", "guarantee", "fund ",
                   "procurement", "auction", "tender", "contract for difference", "contracts for difference",
                   "certificat", "standard", "monitoring, reporting", "verification", "mrv", "permit", "licen",
                   "obligation", "penalt", "research and development", "r&d", "innovation programme", "scheme",
                   "subvención", "subsidio", "incentivo", "préstamo", "licitación", "förderung", "zuschuss",
                   "darlehen", "subvention", "prêt", "補助金", "税制", "补贴", "贷款", "субсид"],
    "demand": ["credit", "offset", "emissions trading", "trading system", "cap-and-trade", "allowance",
               "carbon market", "compliance market", "carbon price", "carbon pricing", "carbon tax", "purchase",
               "procure", "buyer", "demand for", "offtake", "crédit", "mercado de carbono", "bonos de carbono",
               "marché du carbone", "emissionshandel", "zertifikat", "排出量取引", "クレジット", "碳市场",
               "碳交易", "торгов", "배출권"],
    "targets": ["target", "net zero", "net-zero", "carbon neutral", "climate neutral", "neutrality",
                "reduce emissions", "emission reduction", "legally binding", "binding", "commitment", "by 2030",
                "by 2050", "meta", "objectif", "ziel", "neutralidad", "neutralité", "目标", "目標", "цел",
                "re:\\b20[2-6]\\d\\b", "re:\\d+(\\.\\d+)?\\s?%", "re:\\b(mt|gt|kt)\\s?co2",
                "re:(million|billion) (tonnes|tons)"],
    "funding": ["budget", "funding", "financ", "allocated", "appropriat", "investment", "million", "billion",
                "presupuesto", "financiamiento", "financement", "haushalt", "fördermittel", "予算", "资金", "бюджет",
                "re:(€|\\$|£|eur|usd|gbp|aud|cad|inr|rmb|brl)\\s?\\d",
                "re:\\d+([.,]\\d+)?\\s?(million|billion|mio|mrd|bn|crore|lakh)"],
}

# Questions that are only asked when the document mentions their topic often enough
# (several languages). Questions without an entry are always asked.
QUERY_GATES = {
    "methods": ["forest", "afforest", "reforest", "soil", "wetland", "peat", "biochar", "bioenergy", "beccs",
                "direct air", "weathering", "mangrove", "sink", "sequest", "removal", "bosque", "forêt", "floresta",
                "wald", "森林", "林", "碳汇", "лес", "hutan", "산림", "sumidero", "puits", "senke"],
    "storage": ["storage", "ccs", "ccus", "carbon capture", "geological", "injection", "stockage", "captage",
                "almacenamiento", "captura de carbono", "armazenamento", "speicherung", "abscheidung", "貯留",
                "封存", "捕集", "хранени", "저장"],
    "demand": ["credit", "offset", "emissions trading", "trading system", " ets", "carbon market", "procurement",
               "purchase", "contract for difference", "contracts for difference", "crédit", "mercado de carbono",
               "bonos de carbono", "emissionshandel", "排出量取引", "碳市场", "碳交易", "торгов", "배출권"],
    "funding": ["fund", "budget", "million", "billion", "financ", "grant", "loan", "subsid", "eur ", "usd", "$",
                "€", "fondos", "financiamiento", "financement", "förder", "予算", "资金", "资助", "финанс"],
}

_TOC_LINE = re.compile(r"(\.{4,}|…{2,}|(\s\.){3,})\s*\d*\s*$|^\s*[A-Z0-9][^.;:]{15,90}\s\d{1,3}\s*$")
# Heading-only lines of a legal table of contents ("Sec. 11101. Authorization of appropriations.").
_LEGAL_HEADING = re.compile(r"^\s*(sec\.|section|article|art\.|chapter|part|title|subtitle|division)\s*"
                            r"[\dIVXLC]+[\w\-—.:]*\s.{0,90}$", re.IGNORECASE)
_GLYPH_NAMES = re.compile(r"(medial|iolated|initial|final)/", re.IGNORECASE)
BOILERPLATE = ["cookie", "copyright", "all rights reserved", "privacy", "newsletter", "subscribe", "javascript",
               "log in", "sign in", "skip to", "©", "terms of use", "terms and conditions", "accessibility",
               "share this page", "back to top", "breadcrumb", "download notice", "save to my items",
               "news stories, speeches", "nationalarchives", "open government licence"]


def is_noise(text: str) -> bool:
    """Table of contents, website navigation/boilerplate or garbled PDF text."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if not lines:
        return True
    if len(_GLYPH_NAMES.findall(text)) >= 5:
        return True
    letters = sum(ch.isalpha() for ch in text)
    if letters < 0.5 * len(text.replace(" ", "")):
        return True
    toc = sum(bool(_TOC_LINE.search(line) or _LEGAL_HEADING.match(line)) for line in lines)
    if len(lines) >= 4 and toc >= 0.5 * len(lines):
        return True
    lowered = text.casefold()
    boilerplate = sum(lowered.count(word) for word in BOILERPLATE)
    if boilerplate >= 3:
        return True
    # Navigation menus: mostly very short lines plus at least one boilerplate word
    # (legal text split into short lines, e.g. "(", "paragraph 3", ")", has none).
    short = sum(len(line.split()) <= 3 for line in lines)
    return len(lines) >= 10 and short >= 0.7 * len(lines) and boilerplate >= 1


def active_queries(text: str) -> list[str]:
    """Question names to ask for this document (gated questions need enough keyword hits)."""
    lowered = text.casefold()
    names = []
    for name in QUERIES:
        words = QUERY_GATES.get(name)
        if words is None or sum(lowered.count(w) for w in words) >= GATE_MIN_HITS:
            names.append(name)
    return names


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


# Climate/carbon context: in long laws about many topics (e.g. the 700,000-token US
# infrastructure act) generic words like "credit" or "procurement" also occur in
# unrelated sections, so for these variables a passage must also be about carbon.
CONTEXT_TERMS = ["carbon", "co2", "co₂", "greenhouse", "ghg", "emission", "climate", "removal", "sink", "sequest",
                 "forest", "carbono", "carbone", "kohlenstoff", "treibhaus", "emisi", "émission", "炭素", "碳",
                 "温室", "排出", "углерод", "выброс", "karbon", "탄소", "온실"]
NEEDS_CONTEXT = {"instrument", "demand", "funding", "targets"}


def _keyword_matchers(words: list[str]):
    compiled = []
    for word in words:
        if word.startswith("re:"):
            compiled.append(re.compile(word[3:], re.IGNORECASE))
        else:
            compiled.append(word.casefold())
    return compiled


class KeywordRetriever:
    """Targeted keyword search per variable (no model needed).

    A chunk's score for a variable is the sum of log(1 + hits) over that
    variable's keywords, so a passage that mentions several different keywords
    beats one that repeats a single word.
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
        summary = find_summary(text, estimate, min(1200, frame_budget), INTRO_HEADINGS)
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
    cap = max(QUERY_CAP * (budget - used), CHUNK_TOKENS * 1.5)  # at least one chunk per question
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
