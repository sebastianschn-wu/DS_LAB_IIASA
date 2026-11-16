"""Decide which download controls to follow and how to name the saved files.

A control is worth saving when it points at a file, or when it is a button
whose click produces a file. Controls that send the browser to a data-entry
form (Jotform and similar) are rejected. A confirmation dialog that only
asks the user to press Download is not a form.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urljoin, urlsplit

# Kept in sync with the scanner in scrape-downloads.script.py.
DOWNLOAD_SOURCE = r"(?:\b(?:download|export)\b|\.csv\b|\.xlsx?\b|\.zip\b|\bcsv\b)"
DOWNLOAD_RE = re.compile(DOWNLOAD_SOURCE, re.IGNORECASE)

FORM_URL_RE = re.compile(
    r"(?i)(?:"
    r"(?:^|//|\.)(?:jotform\.com|typeform\.com|formstack\.com|wufoo\.com|"
    r"surveymonkey\.com|tally\.so|fillout\.com|paperform\.co|cognitoforms\.com|"
    r"hsforms\.com|forms\.office\.com|forms\.gle|forms\.microsoft\.com)"
    r"|docs\.google\.com/forms"
    r"|airtable\.com/.+/form"
    r")"
)

FILE_CONTENT_TYPES = {
    "text/csv",
    "application/csv",
    "text/tab-separated-values",
    "application/pdf",
    "application/zip",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel.sheet.macroenabled.12",
}

FILE_URL_RE = re.compile(
    r"(?i)(?:\.csv|\.xlsx?|\.zip|\.pdf)(?:$|[?#])|(?:[?&](?:csv|format|download|export)=)"
)

CLIMATE_LAWS_ENV = "https://climate-laws.org/api/env"
CLIMATE_LAWS_THEME = "https://climate-laws.org/api/theme-config"
# Larger pages report 500 hits but return fewer families, and the next
# continuation token skips the ones left out. 20 matches the site's own page.
SEARCH_PAGE_SIZE = 20

_EXTENSIONS = {
    "text/csv": ".csv",
    "application/csv": ".csv",
    "text/tab-separated-values": ".tsv",
    "application/pdf": ".pdf",
    "application/zip": ".zip",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/octet-stream": ".bin",
}

_FORM_HTML_RE = re.compile(
    r"(?i)(?:jotform\.com|typeform\.com|formstack\.com|hsforms\.com|"
    r"type=[\"']email[\"']|name=[\"'](?:email|e-mail|firstname|lastname|"
    r"full_name|organisation|organization|company)[\"'])"
)


def content_type_base(headers: dict[str, str]) -> str:
    return headers.get("content-type", "").split(";", 1)[0].strip().lower()


def is_form_url(url: str) -> bool:
    """True when the URL is a hosted form rather than a file."""
    return bool(url and FORM_URL_RE.search(url))


def html_is_form_gate(html: str) -> bool:
    """True when an HTML body is a form the user would have to fill in."""
    return bool(html and _FORM_HTML_RE.search(html))


def is_download_candidate(text: str, aria: str, href: str, data: str) -> bool:
    """True when the visible label, aria name, href, or data attributes say download.

    Only the first line of the label is used, so a navigation card whose
    description happens to mention the word "download" is left alone.
    """
    short = (text or "").split("\n", 1)[0].strip()[:120]
    return any(DOWNLOAD_RE.search(value or "") for value in (aria, short, href, data))


def actionable_href(href: str, page_url: str) -> str | None:
    """Absolute http(s) URL for a control, or None when the control is a button."""
    if not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
        return None
    absolute = urljoin(page_url, href)
    parsed = urlsplit(absolute)
    if parsed.scheme not in {"http", "https"}:
        return None
    current = urlsplit(page_url)
    same_document = (parsed.scheme, parsed.netloc, parsed.path, parsed.query) == (
        current.scheme,
        current.netloc,
        current.path,
        current.query,
    )
    if same_document:
        return None
    return absolute


def classify_control(href: str, page_url: str) -> str:
    """Return ``form``, ``href``, or ``button``."""
    target = actionable_href(href, page_url)
    if target is None:
        return "button"
    if is_form_url(target):
        return "form"
    return "href"


def is_file_response(headers: dict[str, str], url: str) -> bool:
    """True when response headers describe a downloadable file."""
    disposition = headers.get("content-disposition", "")
    if re.search(r"(?i)\b(?:attachment|filename\*?=)", disposition):
        return True
    base = content_type_base(headers)
    if base in FILE_CONTENT_TYPES:
        return True
    if base == "application/octet-stream" and FILE_URL_RE.search(url):
        return True
    return False


def filename_from_content_disposition(disposition: str) -> str | None:
    if not disposition:
        return None
    encoded = re.search(r"(?i)filename\*\s*=\s*UTF-8''([^;]+)", disposition)
    if encoded:
        return unquote(encoded.group(1).strip().strip('"'))
    quoted = re.search(r'(?i)filename\s*=\s*"([^"]+)"', disposition)
    if quoted:
        return quoted.group(1).strip()
    plain = re.search(r"(?i)filename\s*=\s*([^;]+)", disposition)
    if plain:
        return plain.group(1).strip().strip('"')
    return None


def extension_for(content_type: str) -> str:
    base = content_type.split(";", 1)[0].strip().lower()
    return _EXTENSIONS.get(base, "")


def safe_filename(name: str) -> str:
    """Make a response filename safe to write on disk."""
    cleaned = (name or "").strip().replace("\\", "-").replace("/", "-")
    cleaned = re.sub(r'[<>:"|?*\x00-\x1f]', "-", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    if not cleaned or cleaned in {".", ".."}:
        return "download"
    return cleaned[:180]


def is_climate_laws_search(url: str) -> bool:
    """True for a Climate Laws search page, which is downloaded through its API."""
    parts = urlsplit(url)
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host == "climate-laws.org" and parts.path.rstrip("/") == "/search"


def category_slug(url: str) -> str:
    """The ``c`` query value. An empty value means the whole database."""
    for key, value in parse_qsl(urlsplit(url).query, keep_blank_values=True):
        if key == "c" and value:
            return value
    return "All"


def build_search_body(
    theme: dict,
    category_slug_value: str,
    continuation_tokens: list[str],
    page_size: int = SEARCH_PAGE_SIZE,
    year_range: tuple[str, str] = ("1947", "2027"),
) -> dict:
    """Build the JSON body the Climate Laws site sends for a policies search."""
    options = theme["deprecatedCategories"]["options"]
    chosen = next(
        (option for option in options if str(option.get("slug", "")).lower() == category_slug_value.lower()),
        None,
    )
    if chosen is None:
        known = ", ".join(str(option.get("slug", "")) for option in options)
        raise ValueError(f"unknown Climate Laws category {category_slug_value!r} (known: {known})")
    filters: dict[str, list[str]] = {}
    if chosen.get("category"):
        filters["categories"] = list(chosen["category"])
    return {
        "concept_filters": [],
        "corpus_import_ids": list(chosen["value"]),
        "exact_match": True,
        "keyword_filters": filters,
        "limit": page_size,
        "page_size": page_size,
        "offset": 0,
        "max_passages_per_doc": 50,
        "metadata": [],
        "query_string": "",
        "sort_field": "date",
        "sort_order": "desc",
        "sort_within_page": False,
        "year_range": [year_range[0], year_range[1]],
        "runSearch": True,
        "continuation_tokens": list(continuation_tokens),
    }


def merge_csv_files(paths: list[Path], dest: Path) -> int:
    """Write one CSV. A row that already appeared in an earlier page is left out."""
    header: list[str] | None = None
    seen: set[tuple[str, ...]] = set()
    rows: list[list[str]] = []
    for path in paths:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.reader(handle)
            file_header = next(reader, None)
            if not file_header:
                continue
            if header is None:
                header = file_header
            for row in reader:
                if not any(cell.strip() for cell in row):
                    continue
                key = tuple(row)
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)
    if header is None:
        raise ValueError("no CSV header in the downloaded pages")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    return len(rows)


def site_slug(url: str) -> str:
    host = urlsplit(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    host = host.split(":", 1)[0]
    label = host.rsplit(".", 1)[0] if "." in host else host
    slug = re.sub(r"[^a-z0-9.-]+", "-", label).strip("-")
    return slug or "download"


def prefixed_filename(slug: str, name: str) -> str:
    safe = safe_filename(name)
    prefix = f"{slug}__"
    if safe.startswith(prefix):
        return safe
    return f"{prefix}{safe}"


def filename_for_response(headers: dict[str, str], url: str, slug: str) -> str:
    raw = filename_from_content_disposition(headers.get("content-disposition", ""))
    if not raw:
        raw = Path(urlsplit(url).path).name or "download"
    safe = safe_filename(raw)
    if "." not in Path(safe).name:
        safe += extension_for(headers.get("content-type", "")) or ".bin"
    return prefixed_filename(slug, safe)


def body_looks_like_html(body: bytes) -> bool:
    head = body.lstrip()[:200].lower()
    return head.startswith((b"<!doctype html", b"<html", b"<head", b"<form"))


def allocate_path(directory: Path, filename: str, used: set[Path]) -> Path:
    """Pick a path inside ``directory``. Names already used in this run get a suffix."""
    path = directory / filename
    if path not in used:
        used.add(path)
        return path
    stem = path.stem
    suffix = path.suffix
    number = 2
    while True:
        candidate = directory / f"{stem}-{number}{suffix}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        number += 1
