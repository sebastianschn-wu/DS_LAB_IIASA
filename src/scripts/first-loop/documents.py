"""Download a policy link and extract its text (HTML or PDF), with an on-disk cache.

``fetch_document`` returns a payload dict with the keys from constants
(FETCH_OUTCOME, FETCH_TOKENS, FETCH_TOKENS_LOWER_BOUND, FETCH_TEXT, FETCH_ERROR).
Outcomes: ok, over_threshold, empty, error. Errors are not cached, so they are
retried in the next run.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

from constants import (
    CACHEABLE_OUTCOMES,
    DOWNLOAD_TIMEOUT,
    ENCRYPTED_PDF_ERROR,
    FETCH_ATTEMPTS,
    FETCH_ERROR,
    FETCH_OUTCOME,
    FETCH_TEXT,
    FETCH_TOKENS,
    FETCH_TOKENS_LOWER_BOUND,
    HTML_DROP_TAGS,
    HTML_PARSER,
    HTTP_ACCEPT,
    MAX_DOWNLOAD_BYTES,
    MIN_DOCUMENT_TOKENS,
    OUTCOME_EMPTY,
    OUTCOME_ERROR,
    OUTCOME_OK,
    OUTCOME_OVER_THRESHOLD,
    PDF_EXTENSION,
    PDF_MAGIC,
    TEXT_ENCODING,
    USER_AGENT,
)
from text_utils import estimate_tokens, normalize_text


class DocumentOverThreshold(Exception):
    """The download is too large to be a usable document under the token cap."""


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": HTTP_ACCEPT})
    return session


# ----------------------------------------------------------------------- cache
def cache_path(cache_dir: Path, url: str, max_doc_tokens: int) -> Path:
    digest = hashlib.sha256(f"{max_doc_tokens}|{url}".encode(TEXT_ENCODING)).hexdigest()
    return cache_dir / f"{digest}.json"


def read_cache(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding=TEXT_ENCODING))
    except (OSError, json.JSONDecodeError):
        return None


def write_cache(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding=TEXT_ENCODING)


# ------------------------------------------------------------- text extraction
def decode_bytes(data: bytes, content_type: str) -> str:
    match = re.search(r"charset=([^;\s]+)", content_type, flags=re.IGNORECASE)
    encoding = match.group(1).strip("\"'") if match else TEXT_ENCODING
    try:
        return data.decode(encoding, errors="replace")
    except LookupError:
        return data.decode(TEXT_ENCODING, errors="replace")


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, HTML_PARSER)
    for tag in soup(HTML_DROP_TAGS):
        tag.decompose()
    return normalize_text(soup.get_text("\n"))


def first_pdf_link(html: str, base_url: str) -> str:
    soup = BeautifulSoup(html, HTML_PARSER)
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if PDF_EXTENSION in href.lower():
            return urljoin(base_url, href)
    return ""


def pdf_to_text(data: bytes, max_doc_tokens: int) -> tuple[str, int, bool]:
    """Return (text, tokens, over_threshold). Stops reading once the cap is passed."""
    reader = PdfReader(BytesIO(data))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise ValueError(ENCRYPTED_PDF_ERROR) from exc
    parts: list[str] = []
    tokens = 0
    for page in reader.pages:
        try:
            extracted = page.extract_text() or ""
        except Exception:
            continue
        cleaned = normalize_text(extracted)
        if not cleaned:
            continue
        parts.append(cleaned)
        tokens += estimate_tokens(cleaned) + 1
        if tokens > max_doc_tokens:
            return "", tokens, True
    text = "\n".join(parts)
    return text, estimate_tokens(text), False


def is_pdf(url: str, content_type: str, data: bytes) -> bool:
    if data.startswith(PDF_MAGIC):
        return True
    if PDF_EXTENSION.lstrip(".") in content_type.lower():
        return True
    return url.split("?", 1)[0].lower().endswith(PDF_EXTENSION)


# -------------------------------------------------------------------- download
def download(session: requests.Session, url: str) -> tuple[bytes, str, str]:
    response = session.get(url, timeout=DOWNLOAD_TIMEOUT, allow_redirects=True, stream=True)
    response.raise_for_status()
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_content(chunk_size=65536):
        if not chunk:
            continue
        total += len(chunk)
        if total > MAX_DOWNLOAD_BYTES:
            response.close()
            raise DocumentOverThreshold(f"download exceeded {MAX_DOWNLOAD_BYTES} bytes")
        chunks.append(chunk)
    return b"".join(chunks), response.headers.get("Content-Type", ""), response.url


def fetch_payload(outcome: str, tokens: int, lower_bound: bool, text: str, error: str = "") -> dict[str, Any]:
    payload: dict[str, Any] = {
        FETCH_OUTCOME: outcome,
        FETCH_TOKENS: tokens,
        FETCH_TOKENS_LOWER_BOUND: lower_bound,
        FETCH_TEXT: text,
    }
    if error:
        payload[FETCH_ERROR] = error
    return payload


def classify_text(text: str, max_doc_tokens: int, lower_bound: bool = False) -> dict[str, Any]:
    tokens = estimate_tokens(text)
    if tokens > max_doc_tokens:
        return fetch_payload(OUTCOME_OVER_THRESHOLD, tokens, lower_bound, "")
    if tokens < MIN_DOCUMENT_TOKENS:
        return fetch_payload(OUTCOME_EMPTY, tokens, False, "")
    return fetch_payload(OUTCOME_OK, tokens, False, text)


def fetch_document(session: requests.Session, url: str, max_doc_tokens: int, cache_dir: Path) -> dict[str, Any]:
    """Download ``url`` and return its text payload (cached per URL and token cap).

    An HTML landing page with almost no text but a PDF link is followed to the PDF.
    """
    path = cache_path(cache_dir, url, max_doc_tokens)
    cached = read_cache(path)
    if cached and cached.get(FETCH_OUTCOME) in CACHEABLE_OUTCOMES:
        return cached

    def attempt(target: str, allow_pdf_hop: bool) -> dict[str, Any]:
        data, content_type, final_url = download(session, target)
        if is_pdf(final_url, content_type, data):
            text, tokens, over = pdf_to_text(data, max_doc_tokens)
            if over:
                return fetch_payload(OUTCOME_OVER_THRESHOLD, tokens, True, "")
            return classify_text(text, max_doc_tokens)
        html = decode_bytes(data, content_type)
        if allow_pdf_hop:
            pdf_url = first_pdf_link(html, final_url)
            if pdf_url and pdf_url != target and estimate_tokens(html_to_text(html)) < MIN_DOCUMENT_TOKENS:
                return attempt(pdf_url, allow_pdf_hop=False)
        return classify_text(html_to_text(html), max_doc_tokens)

    last_error = ""
    for try_index in range(FETCH_ATTEMPTS):
        try:
            fetched = attempt(url, allow_pdf_hop=True)
            write_cache(path, fetched)
            return fetched
        except DocumentOverThreshold:
            fetched = fetch_payload(OUTCOME_OVER_THRESHOLD, max_doc_tokens + 1, True, "")
            write_cache(path, fetched)
            return fetched
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if try_index < FETCH_ATTEMPTS - 1:
                time.sleep(1.5)
    return fetch_payload(OUTCOME_ERROR, 0, False, "", last_error)
