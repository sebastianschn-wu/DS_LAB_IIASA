"""Download a Climate Laws search through the public Climate Policy Radar API.

The website publishes its API root and app token at
``https://climate-laws.org/api/env``. The same token is what the download
button sends. ``POST /searches/download-csv`` returns one window of the
CSV. The next window is selected with the ``continuation_token`` from
``POST /searches``. A browser is not required.
"""

from __future__ import annotations

import csv
import shutil
from pathlib import Path

import requests

from download_controls import (
    CLIMATE_LAWS_ENV,
    CLIMATE_LAWS_THEME,
    SEARCH_PAGE_SIZE,
    build_search_body,
    category_slug,
    merge_csv_files,
    site_slug,
)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
MAX_PAGES = 400


def _session(referer: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Origin": "https://climate-laws.org",
            "Referer": referer,
        }
    )
    return session


def download_climate_laws(url: str, output_dir: Path) -> list[Path]:
    """Page the search API and write one CSV for ``url``."""
    print(f"\n{url}")
    output_dir.mkdir(parents=True, exist_ok=True)
    session = _session(url)
    env = session.get(CLIMATE_LAWS_ENV, timeout=30).json()["env"]
    api = str(env["api_url"]).rstrip("/")
    session.headers["app-token"] = env["app_token"]
    theme = session.get(CLIMATE_LAWS_THEME, timeout=30).json()
    slug = category_slug(url)
    print(f"  api {api}")
    print(f"  category {slug}")

    parts_dir = output_dir / f".{site_slug(url)}-pages"
    if parts_dir.exists():
        shutil.rmtree(parts_dir)
    parts_dir.mkdir(parents=True)
    part_paths: list[Path] = []
    tokens: list[str] = []
    seen_tokens: set[str] = set()
    reported_total: int | None = None
    try:
        for page_index in range(MAX_PAGES):
            body = build_search_body(theme, slug, tokens, page_size=SEARCH_PAGE_SIZE)
            search = session.post(f"{api}/searches", json=body, timeout=120)
            search.raise_for_status()
            payload = search.json()
            families = payload.get("families") or []
            reported_total = payload.get("total_family_hits", reported_total)
            csv_response = session.post(f"{api}/searches/download-csv", json=body, timeout=180)
            csv_response.raise_for_status()
            content_type = csv_response.headers.get("content-type", "")
            if "csv" not in content_type and not csv_response.content.startswith(b"Collection"):
                detail = csv_response.content[:160]
                raise RuntimeError(f"download-csv returned {content_type or csv_response.status_code}: {detail!r}")
            part = parts_dir / f"page-{page_index:03d}.csv"
            part.write_bytes(csv_response.content)
            part_paths.append(part)
            print(
                f"  page {page_index + 1}: {len(families)} families, "
                f"{len(csv_response.content)} bytes (reported total {reported_total})"
            )
            nxt = payload.get("continuation_token") or ""
            if not families or not nxt or nxt in seen_tokens:
                break
            seen_tokens.add(nxt)
            tokens = [nxt]
        else:
            raise RuntimeError(f"stopped after {MAX_PAGES} API pages")
        if not part_paths:
            print("  no pages downloaded")
            return []
        merged = output_dir / f"{site_slug(url)}__search_results.csv"
        row_count = merge_csv_files(part_paths, merged)
        with merged.open(newline="", encoding="utf-8") as handle:
            family_count = len({row.get("Family URL", "") for row in csv.DictReader(handle)})
        print(
            f"  saved {merged} ({family_count} policies, {row_count} document rows, "
            f"{len(part_paths)} API pages, reported policies {reported_total})"
        )
        return [merged]
    finally:
        shutil.rmtree(parts_dir, ignore_errors=True)
