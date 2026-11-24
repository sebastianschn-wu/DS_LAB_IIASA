"""Settings of the RAG context (``rag.py``), with the reasoning behind each value.

References used below:

[1] Liu et al. (2024). Lost in the Middle: How Language Models Use Long Contexts.
    TACL 12, 157-173. https://doi.org/10.1162/tacl_a_00638
[2] Gao et al. (2023). Retrieval-Augmented Generation for Large Language Models: A Survey.
    https://arxiv.org/abs/2312.10997
[3] Rethinking Chunk Size for Long-Document Retrieval: A Multi-Dataset Analysis (2025).
    https://arxiv.org/abs/2505.21700
[4] Montague & Aslam (2001). Relevance Score Normalization for Metasearch. CIKM 2001.
    https://www.khoury.northeastern.edu/home/jaa/papers/MontagueAs01b.pdf
[5] Robertson & Zaragoza (2009). The Probabilistic Relevance Framework: BM25 and Beyond.
    Foundations and Trends in Information Retrieval 3(4), 333-389.
    https://doi.org/10.1561/1500000019
[6] Manning, Raghavan & Schütze (2008). Introduction to Information Retrieval, section 11.4.3
    (Okapi BM25). Cambridge University Press.
    https://nlp.stanford.edu/IR-book/html/htmledition/okapi-bm25-a-non-binary-model-1.html
[7] Chen et al. (2024). BGE M3-Embedding: Multi-Lingual, Multi-Functionality,
    Multi-Granularity Text Embeddings. https://arxiv.org/abs/2402.03216

Values without a reference were set by inspecting what RAG version 1 sent to the
model (``results/baseline/rag_inspection.md``) and are limited by our hardware:
qwen2.5:7b runs locally with a 6000-token document budget (``--max-doc-tokens``).
"""

# Version 2: noise filter, z-score selection, larger frame (results: rag2).
# Version 3: no keyword gates, multilingual keyword dictionary (constants/keywords.json).
RAG_VERSION = 3

# --------------------------------------------------------------- the frame
# About 30% of the budget goes to the document's own summary (or introduction) and
# its beginning, so the model knows what kind of document it reads (title, purpose,
# scope) before it sees passages out of context. Models use information at the start
# of the input best [1]; Policy_scope, our most accurate field, depends on it.
FRAME_SHARE = 0.3
SUMMARY_MAX_TOKENS = 1800       # a summary longer than this is cut (most fit, see rag_inspection.md)
SUMMARY_MIN_TOKENS = 80         # less text under a "Summary" heading = table-of-contents entry
INTRO_MAX_TOKENS = 1200         # introductions ramble more than summaries, so a smaller cap
LEAD_TOKENS = 600               # minimum share of the beginning (title, preamble, article 1)
HEADING_MAX_CHARS = 120         # longer lines are sentences, not headings

# --------------------------------------------------------------- chunks
# Fixed-size chunks along paragraph boundaries. Fixed-size chunking is the common
# default in RAG (e.g. chunks of 200 tokens [2]); [3] finds small
# chunks best for short factual answers and 512-1024 tokens best for answers spread
# over longer text. Our answers are mostly one clause or article (a target, a funding
# amount, an instrument), so we stay in between: 350 tokens keep a legal article
# together and still let about 12 passages fit into the retrieval budget.
CHUNK_TOKENS = 350

# --------------------------------------------------------------- selection
# Scores of different questions are not comparable (a document full of "forest"
# gives high keyword scores for methods everywhere), so each question's scores are
# z-normalised within the document, the standard unsupervised normalisation for
# comparing scores from different queries/systems [4]. A chunk is taken when it is at
# least one standard deviation above the document mean for a question: if scores
# were roughly normal that is the top ~16% of chunks, i.e. only clearly relevant
# passages, never a fixed quota per question. MIN_Z = 1.0 is our choice, set after
# inspecting version 1 (fixed top-k sent many unrelated passages for questions the
# document does not address); it is not taken from another study.
MIN_Z = 1.0
# One question fills at most 30% of the retrieval budget, so a long document about
# one topic (e.g. a forest law) still leaves room for the other questions.
QUERY_CAP = 0.3
# ... but always enough for at least one chunk per question (short budgets).
QUERY_CAP_MIN_CHUNKS = 1.5

# --------------------------------------------------------------- retrievers
# BM25 parameters [5, 6]. k1 controls how fast repeated occurrences of a query term
# stop adding to the score (k1 = 0: only presence counts; large k1: raw counts).
# b controls length normalisation (b = 1: full normalisation by chunk length, b = 0:
# none). [6] recommends k1 between 1.2 and 2 and b = 0.75 when there is no tuning
# data; we use the middle of that k1 range because our chunks are long legal text in
# which a relevant term often occurs several times.
BM25_K1 = 1.5
BM25_B = 0.75

# Ollama embedding retriever: bge-m3 is multilingual (100+ languages) and supports
# inputs up to 8192 tokens [7], so English questions also find passages in the other
# languages of our documents.
DEFAULT_EMBED_MODEL = "bge-m3"
EMBED_BATCH = 32
EMBED_TIMEOUT = 300

GAP = "[...]"

# --------------------------------------------------------------- questions
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

# Every question is asked for every document (no keyword gates since version 3):
# all of them serve variables the codebook codes for every policy (Funding_sum,
# Value_chain_focus, Specific_method, ...). A question whose topic the document does
# not mention gets no passages anyway, because a chunk must have a positive score
# and z >= MIN_Z.

# In long laws about many topics (e.g. the 700,000-token US infrastructure act)
# generic words like "credit" or "procurement" also occur in unrelated sections, so
# for these questions a passage must also mention carbon/climate (CONTEXT_TERMS).
NEEDS_CONTEXT = {"instrument", "demand", "funding", "targets"}

# --------------------------------------------------------------- headings
SUMMARY_HEADINGS = [
    "executive summary", "summary", "abstract", "overview", "synopsis", "key messages", "highlights",
    "summary for policymakers", "résumé", "resume", "synthèse", "resumen ejecutivo", "resumen", "sumário executivo",
    "sumário", "resumo", "zusammenfassung", "kurzfassung", "überblick", "sintesi", "riassunto", "ringkasan",
    "ikhtisar", "краткое содержание", "резюме", "概要", "要旨", "摘要", "概述", "要点", "요약", "개요",
    "yönetici özeti", "özet", "الملخص التنفيذي", "ملخص",
]
# Used when there is no summary: the introduction usually says what the document does.
INTRO_HEADINGS = [
    "introduction", "introducción", "introdução", "introduzione", "einleitung", "einführung", "pendahuluan",
    "введение", "はじめに", "序言", "引言", "前言", "서론", "background and purpose", "giriş", "مقدمة",
]

# --------------------------------------------------------------- noise filter
# Website navigation and copyright boilerplate; three hits in one chunk = noise.
BOILERPLATE = ["cookie", "copyright", "all rights reserved", "privacy", "newsletter", "subscribe", "javascript",
               "log in", "sign in", "skip to", "©", "terms of use", "terms and conditions", "accessibility",
               "share this page", "back to top", "breadcrumb", "download notice", "save to my items",
               "news stories, speeches", "nationalarchives", "open government licence"]
BOILERPLATE_MIN_HITS = 3
GLYPH_NAMES_MIN_HITS = 5        # garbled Arabic PDF text ("medial/", "initial/" glyph names)
MIN_LETTER_SHARE = 0.5          # less than half letters = tables of numbers or broken extraction
TOC_MIN_LINES = 4
TOC_LINE_SHARE = 0.5            # half the lines look like table-of-contents entries
MENU_MIN_LINES = 10
MENU_SHORT_LINE_WORDS = 3
MENU_SHORT_LINE_SHARE = 0.7
