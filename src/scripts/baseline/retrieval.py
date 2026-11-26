"""Source retrieval for the unbiased baseline: full text, input type, excerpt.

The first loop drops a document that is longer than the token limit and then
sends the expert ``CDR_link`` summary instead. Here no expert text is ever used:

* the full document is downloaded (PDF or webpage), with the first loop's own
  download and text-extraction functions,
* long documents are shortened to the most relevant passages (``excerpt``),
* every source is labelled with one of three input types, so results can be
  reported separately:

  ``policy_text``          the policy itself (PDF, or a long legal/official text page)
  ``webpage_description``  a webpage that describes the policy (database entry,
                           landing page, news page), not the policy text
  ``no_text``              nothing usable could be retrieved

The functions take the loaded first-loop module as ``fl`` so this file does not
import the first loop's ``constants`` module itself. Settings are in
``constants/retrieval_settings.py`` of this folder.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from constants.retrieval_settings import (
    CACHE_ENCODING,
    CHUNK_TOKENS,
    DESCRIPTION_DOMAINS,
    EXCERPT_KEYWORDS,
    FETCH_ATTEMPTS,
    FETCH_RETRY_SECONDS,
    FULL_TEXT_TOKEN_LIMIT,
    GAP,
    INPUT_NO_TEXT,
    INPUT_POLICY_TEXT,
    INPUT_SUMMARY,  # noqa: F401  (used as retrieval.INPUT_SUMMARY by baseline.script.py)
    INPUT_TYPES,
    INPUT_WEBPAGE,
    LEAD_MAX_SHARE,
    LEAD_TOKENS,
    LONG_HTML_TOKENS,
    MIN_TEXT_TOKENS,
    OUTCOME_EMPTY,
    OUTCOME_ERROR,
    OUTCOME_OK,
    OUTCOME_TOO_LARGE,
    PARAGRAPH_SPLIT,
)


# ------------------------------------------------------------------ helpers
def domain_of(url: str) -> str:
    host = (urlparse(url or "").hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def is_description_domain(url: str) -> bool:
    host = domain_of(url)
    return any(host == d or host.endswith("." + d) for d in DESCRIPTION_DOMAINS)


def cache_file(cache_dir: Path, url: str) -> Path:
    digest = hashlib.sha256(f"full|{url}".encode(CACHE_ENCODING)).hexdigest()
    return cache_dir / f"{digest}.json"


def result(outcome: str, text: str = "", tokens: int = 0, is_pdf: bool = False,
           final_url: str = "", followed_pdf: bool = False, error: str = "") -> dict[str, Any]:
    return {
        "outcome": outcome,
        "text": text,
        "tokens": tokens,
        "is_pdf": is_pdf,
        "final_url": final_url,
        "followed_pdf": followed_pdf,
        "error": error,
    }


# ---------------------------------------------------------------- download
def _extract(fl, session, url: str) -> dict[str, Any]:
    """Download one URL and return its full text (no token limit)."""
    data, content_type, final_url = fl.download(session, url)
    if fl.is_pdf(final_url, content_type, data):
        text, tokens, _ = fl.pdf_to_text(data, FULL_TEXT_TOKEN_LIMIT)
        outcome = OUTCOME_OK if tokens >= MIN_TEXT_TOKENS else OUTCOME_EMPTY
        return result(outcome, text if outcome == OUTCOME_OK else "", tokens, True, final_url)
    html = fl.decode_bytes(data, content_type)
    text = fl.html_to_text(html)
    tokens = fl.estimate_tokens(text)
    page = result(OUTCOME_OK if tokens >= MIN_TEXT_TOKENS else OUTCOME_EMPTY,
                  text if tokens >= MIN_TEXT_TOKENS else "", tokens, False, final_url)
    page["_html"] = html
    return page


def fetch_full(fl, session, url: str, cache_dir: Path) -> dict[str, Any]:
    """Full text of the policy link, cached on disk.

    A PDF linked from a policy-database page (or from an almost empty page) is
    fetched instead of the page, because it is usually the policy itself.
    """
    path = cache_file(cache_dir, url)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding=CACHE_ENCODING))
        except (OSError, json.JSONDecodeError):
            pass

    last_error = ""
    fetched: dict[str, Any] | None = None
    for attempt in range(FETCH_ATTEMPTS):
        try:
            fetched = _extract(fl, session, url)
            break
        except fl.DocumentOverThreshold as exc:
            fetched = result(OUTCOME_TOO_LARGE, error=str(exc))
            break
        except Exception as exc:  # network errors, HTTP errors, broken files
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt == 0:
                time.sleep(FETCH_RETRY_SECONDS)
    if fetched is None:
        # Errors are not cached, so a later run tries again.
        return result(OUTCOME_ERROR, error=last_error)

    html = fetched.pop("_html", "")
    if html and not fetched["is_pdf"]:
        page_url = fetched["final_url"] or url
        if is_description_domain(page_url) or fetched["outcome"] == OUTCOME_EMPTY:
            pdf_url = fl.first_pdf_link(html, page_url)
            if pdf_url and pdf_url != url:
                try:
                    pdf = _extract(fl, session, pdf_url)
                    pdf.pop("_html", None)
                    if pdf["outcome"] == OUTCOME_OK and pdf["is_pdf"]:
                        pdf["followed_pdf"] = True
                        fetched = pdf
                except Exception:
                    pass  # keep the page text

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fetched, ensure_ascii=False), encoding=CACHE_ENCODING)
    return fetched


# -------------------------------------------------------------- input type
def classify(fetched: dict[str, Any], link: str) -> tuple[str, str]:
    """Return (input type, reason)."""
    if fetched.get("outcome") != OUTCOME_OK or not fetched.get("text"):
        return INPUT_NO_TEXT, fetched.get("error") or fetched.get("outcome") or "no text"
    if fetched.get("is_pdf"):
        return INPUT_POLICY_TEXT, "pdf linked from page" if fetched.get("followed_pdf") else "pdf"
    url = fetched.get("final_url") or link
    if is_description_domain(url) or is_description_domain(link):
        return INPUT_WEBPAGE, f"policy database page ({domain_of(url)})"
    if int(fetched.get("tokens") or 0) >= LONG_HTML_TOKENS:
        return INPUT_POLICY_TEXT, f"long webpage (>= {LONG_HTML_TOKENS} tokens)"
    return INPUT_WEBPAGE, f"short webpage (< {LONG_HTML_TOKENS} tokens)"


def read_overrides(path: Path) -> dict[str, str]:
    """Manual corrections: sheet_row -> input type (file may be missing or empty)."""
    import csv

    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    overrides = {}
    for row in rows:
        key = (row.get("sheet_row") or "").strip()
        value = (row.get("input_type") or "").strip()
        if key and value:
            if value not in INPUT_TYPES:
                raise SystemExit(f"Unknown input_type '{value}' for row {key} in {path}")
            overrides[key] = value
    return overrides


# ----------------------------------------------------------------- excerpt
def _score(chunk: str) -> int:
    """Number of excerpt keyword occurrences in the chunk.

    Chunks are ranked by this score, so a relevant passage without any of the
    keywords can be left out; see the reasoning and limits at ``EXCERPT_KEYWORDS``
    in ``constants/retrieval_settings.py`` (the RAG context is the targeted fix).
    """
    lowered = chunk.casefold()
    return sum(lowered.count(word) for word in EXCERPT_KEYWORDS)


def chunks_of(text: str, estimate, size: int = CHUNK_TOKENS) -> list[str]:
    """Group paragraphs into chunks of about ``size`` tokens (long paragraphs are cut)."""
    pieces: list[str] = []
    for paragraph in PARAGRAPH_SPLIT.split(text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        while estimate(paragraph) > size * 2:
            cut = max(1, len(paragraph) * size // max(1, estimate(paragraph)))
            pieces.append(paragraph[:cut])
            paragraph = paragraph[cut:]
        pieces.append(paragraph)
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for piece in pieces:
        piece_tokens = estimate(piece) + 1
        if current and current_tokens + piece_tokens > size:
            chunks.append("\n".join(current))
            current, current_tokens = [], 0
        current.append(piece)
        current_tokens += piece_tokens
    if current:
        chunks.append("\n".join(current))
    return chunks


def excerpt(text: str, budget: int, estimate) -> tuple[str, bool]:
    """Shorten ``text`` to about ``budget`` tokens.

    Keeps the beginning (title, purpose, scope) and then the passages with the
    most CDR and instrument keywords, in their original order. Returns the text
    and whether it was shortened.
    """
    if estimate(text) <= budget:
        return text, False
    chunks = chunks_of(text, estimate)
    chosen: set[int] = set()
    used = 0
    lead_budget = min(LEAD_TOKENS, budget // LEAD_MAX_SHARE)
    for index, chunk in enumerate(chunks):
        size = estimate(chunk)
        if used + size > lead_budget:
            break
        chosen.add(index)
        used += size
    ranked = sorted(
        (i for i in range(len(chunks)) if i not in chosen),
        key=lambda i: (-_score(chunks[i]), i),
    )
    for index in ranked:
        if _score(chunks[index]) == 0:
            break
        size = estimate(chunks[index])
        if used + size > budget:
            continue
        chosen.add(index)
        used += size
    # Fill what is left of the budget with the text that follows the beginning.
    for index, chunk in enumerate(chunks):
        if index in chosen:
            continue
        size = estimate(chunk)
        if used + size > budget:
            break
        chosen.add(index)
        used += size
    parts: list[str] = []
    previous = -1
    for index in sorted(chosen):
        if previous >= 0 and index != previous + 1:
            parts.append(GAP)
        parts.append(chunks[index])
        previous = index
    return "\n".join(parts), True
