#!/usr/bin/env python3
"""Download policy datasets from pages that expose a download control.

Opens each target page, finds download links and buttons, and writes the
files to ``data/downloads``. A link that already points at a file is
requested and saved. A button with no file URL is clicked, and a following
confirmation button (terms of use, then Download) is clicked as well. The
script listens for the file the page then produces, including a CSV built
by the page's own JavaScript.

A control is skipped when it leads to a form: a Jotform (or similar) URL,
a popup whose page asks for an email or other details, or a dialog that
contains those fields. A dialog with only a Download button is kept.

Climate Laws does not need the browser. The site publishes its API root
and app token at ``/api/env``. The script reads that token and pages
``POST /searches/download-csv`` with the continuation token from
``POST /searches`` until the result set is exhausted.

Targets:
    https://climate-laws.org/search?c=policies
    https://www.iea.org/policies

Setup:
    pip install playwright
    python -m playwright install chromium

Usage:
    python src/scripts/scrape-downloads/scrape-downloads.script.py
    python src/scripts/scrape-downloads/scrape-downloads.script.py --headed
    python src/scripts/scrape-downloads/scrape-downloads.script.py --url https://www.iea.org/policies
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from climate_api import download_climate_laws
from download_controls import (
    DOWNLOAD_SOURCE,
    actionable_href,
    allocate_path,
    body_looks_like_html,
    classify_control,
    filename_for_response,
    html_is_form_gate,
    is_climate_laws_search,
    is_file_response,
    is_form_url,
    prefixed_filename,
    safe_filename,
    site_slug,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "downloads"
DEFAULT_URLS = (
    "https://climate-laws.org/search?c=policies",
    "https://www.iea.org/policies",
)
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

_SCAN_JS = r"""
() => {
  const downloadRe = /__PATTERN__/i;
  function isVisible(el) {
    if (!el.getClientRects().length) return false;
    for (let node = el; node && node.nodeType === 1; node = node.parentElement) {
      const style = getComputedStyle(node);
      if (style.display === "none" || style.visibility === "hidden" || style.pointerEvents === "none") {
        return false;
      }
      if (Number.parseFloat(style.opacity) === 0) return false;
    }
    return true;
  }
  const controls = [];
  for (const el of document.querySelectorAll("a, button")) {
    const rawText = (el.innerText || "").trim();
    const shortText = rawText.split("\n")[0].trim().slice(0, 120);
    const aria = (el.getAttribute("aria-label") || "").trim();
    const title = (el.getAttribute("title") || "").trim();
    const hrefAttr = el.getAttribute("href") || "";
    const href = el.href || hrefAttr;
    const data = [...el.attributes]
      .filter((attr) => attr.name.startsWith("data-") && attr.name !== "data-scrape-dl")
      .map((attr) => attr.value)
      .join(" ");
    const matched = [aria, title, shortText, href, data].some((value) => downloadRe.test(value));
    if (!matched || !isVisible(el)) continue;
    const id = String(controls.length);
    el.setAttribute("data-scrape-dl", id);
    const inDialog = Boolean(el.closest("[role='dialog'], dialog, .fixed.inset-0"));
    controls.push({
      id,
      key: [el.tagName, aria || shortText, href].join("\n"),
      tag: el.tagName,
      text: shortText,
      aria,
      href,
      data,
      inDialog,
    });
  }
  return controls;
}
""".replace("__PATTERN__", DOWNLOAD_SOURCE)

_DIALOG_IS_FORM_JS = r"""
() => {
  function isVisible(el) {
    if (!el.getClientRects().length) return false;
    for (let node = el; node && node.nodeType === 1; node = node.parentElement) {
      const style = getComputedStyle(node);
      if (style.display === "none" || style.visibility === "hidden" || style.pointerEvents === "none") {
        return false;
      }
      if (Number.parseFloat(style.opacity) === 0) return false;
    }
    return true;
  }
  const dialogs = [...document.querySelectorAll("[role='dialog'], dialog, .fixed.inset-0")]
    .filter((dialog) => /download/i.test(dialog.innerText || ""));
  for (const dialog of dialogs) {
    if (!isVisible(dialog)) continue;
    const fields = dialog.querySelectorAll(
      "input[type='email'], input[type='text'], input[type='tel'], textarea, select"
    );
    const visibleFields = [...fields].filter(isVisible);
    if (visibleFields.length >= 2) return true;
    if (visibleFields.some((el) => /email|e-mail|name|organisation|organization|company/i.test(
      `${el.name} ${el.id} ${el.placeholder} ${el.type}`
    ))) return true;
  }
  return false;
}
"""


def _label(control: dict) -> str:
    return control.get("aria") or control.get("text") or control.get("tag") or "download"


def _dismiss_cookies(page) -> None:
    """Close a cookie banner so it cannot cover the download control."""
    for pattern in (
        r"^reject( all)?$",
        r"^decline( all)?$",
        r"^deny$",
        r"^accept( all)?$",
        r"^allow( all)?$",
        r"^i agree$",
        r"^got it$",
    ):
        locator = page.get_by_role("button", name=re.compile(pattern, re.IGNORECASE))
        try:
            if locator.count() and locator.first.is_visible():
                locator.first.click(timeout=2000)
                page.wait_for_timeout(400)
                return
        except Exception:
            continue


def _rebind(page, control: dict) -> dict | None:
    """Find the same control again so its click id matches the current DOM."""
    for item in _scan(page):
        if item["key"] == control["key"]:
            return item
    return None


def _scan(page) -> list[dict]:
    return page.evaluate(_SCAN_JS)


def _click(page, control: dict) -> None:
    locator = page.locator(f'[data-scrape-dl="{control["id"]}"]')
    try:
        locator.click(timeout=8000)
        return
    except Exception as first_error:
        try:
            locator.evaluate("el => el.click()")
        except Exception:
            raise first_error


def _display(path: Path) -> Path:
    try:
        return path.relative_to(REPO_ROOT)
    except ValueError:
        return path


def _save_bytes(path: Path, body: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    print(f"  saved {_display(path)} ({len(body)} bytes)")
    return path


def _download_href(context, file_url: str, referer: str, slug: str, output_dir: Path, used: set[Path]) -> Path | None:
    response = context.request.get(
        file_url,
        headers={"Referer": referer},
        timeout=180_000,
    )
    final_url = response.url
    if is_form_url(final_url):
        print(f"  skip: redirected to a form ({final_url})")
        return None
    headers = dict(response.headers)
    if not response.ok:
        print(f"  skip: HTTP {response.status} for {final_url}")
        return None
    if "html" in headers.get("content-type", "").lower():
        text = response.text()
        if html_is_form_gate(text) or is_form_url(final_url):
            print(f"  skip: form page ({final_url})")
            return None
        print(f"  skip: link is a web page, not a file ({final_url})")
        return None
    if not is_file_response(headers, final_url):
        print(f"  skip: not a file ({headers.get('content-type', 'unknown')})")
        return None
    body = response.body()
    if body_looks_like_html(body) and html_is_form_gate(body.decode("utf-8", "replace")):
        print(f"  skip: form page ({final_url})")
        return None
    if len(body) < 32:
        print(f"  skip: empty response from {final_url}")
        return None
    path = allocate_path(output_dir, filename_for_response(headers, final_url, slug), used)
    return _save_bytes(path, body)


def _save_browser_download(download, slug: str, output_dir: Path, used: set[Path]) -> Path | None:
    failure = download.failure()
    if failure:
        print(f"  skip: browser download failed ({failure})")
        return None
    filename = prefixed_filename(slug, safe_filename(download.suggested_filename or "download"))
    path = allocate_path(output_dir, filename, used)
    path.parent.mkdir(parents=True, exist_ok=True)
    download.save_as(str(path))
    print(f"  saved {_display(path)} ({path.stat().st_size} bytes)")
    return path


def _save_playwright_response(response, slug: str, output_dir: Path, used: set[Path]) -> Path | None:
    headers = dict(response.headers)
    try:
        body = response.body()
    except Exception as exc:
        print(f"  skip: could not read the file response ({exc})")
        return None
    if body_looks_like_html(body):
        if html_is_form_gate(body.decode("utf-8", "replace")):
            print(f"  skip: form page ({response.url})")
        return None
    if len(body) < 32:
        return None
    path = allocate_path(output_dir, filename_for_response(headers, response.url, slug), used)
    return _save_bytes(path, body)


def _popup_is_form(popup) -> bool:
    try:
        popup.wait_for_load_state("domcontentloaded", timeout=10_000)
    except Exception:
        return False
    if is_form_url(popup.url):
        return True
    try:
        return html_is_form_gate(popup.content())
    except Exception:
        return False


def _trigger_button(
    page,
    context,
    control: dict,
    known: set[str],
    downloads: list,
    file_responses: list,
    popups: list,
    slug: str,
    output_dir: Path,
    used: set[Path],
    timeout_s: float,
) -> list[Path]:
    """Click a button and follow one confirmation click. Skip the control if a form opens."""
    label = _label(control)
    current = _rebind(page, control)
    if current is None:
        print(f"  skip: {label} is no longer on the page")
        return []
    print(f"  click {label}")
    start_downloads = len(downloads)
    start_responses = len(file_responses)
    start_popups = len(popups)
    url_before = page.url
    try:
        _click(page, current)
    except Exception as exc:
        print(f"  skip: could not click {label} ({exc})")
        return []

    follows = 0
    saw_response_at = None
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if len(popups) > start_popups and _popup_is_form(popups[-1]):
            print(f"  skip {label}: opened a form ({popups[-1].url})")
            try:
                popups[-1].close()
            except Exception:
                pass
            return []
        if page.url != url_before and (is_form_url(page.url) or html_is_form_gate(page.content())):
            print(f"  skip {label}: opened a form ({page.url})")
            try:
                page.go_back(wait_until="domcontentloaded", timeout=15_000)
            except Exception:
                pass
            return []
        if len(downloads) > start_downloads:
            saved = []
            for download in downloads[start_downloads:]:
                path = _save_browser_download(download, slug, output_dir, used)
                if path is not None:
                    saved.append(path)
            return saved
        if len(file_responses) > start_responses:
            if saw_response_at is None:
                saw_response_at = time.time()
            elif time.time() - saw_response_at >= 2:
                saved = []
                for response in file_responses[start_responses:]:
                    path = _save_playwright_response(response, slug, output_dir, used)
                    if path is not None:
                        saved.append(path)
                return saved
        if page.evaluate(_DIALOG_IS_FORM_JS):
            print(f"  skip {label}: download opens a form")
            return []
        if follows < 1:
            fresh = _scan(page)
            new_controls = [
                item for item in fresh if item["key"] not in known and item.get("inDialog")
            ]
            if new_controls:
                follow = new_controls[0]
                known.add(follow["key"])
                kind = classify_control(follow.get("href") or "", page.url)
                follow_label = _label(follow)
                if kind == "form":
                    print(f"  skip {follow_label}: form {follow.get('href')}")
                    return []
                if kind == "href":
                    target = actionable_href(follow.get("href") or "", page.url)
                    print(f"  open {follow_label}")
                    path = _download_href(context, target, page.url, slug, output_dir, used)
                    return [path] if path is not None else []
                print(f"  click {follow_label}")
                try:
                    _click(page, follow)
                except Exception as exc:
                    print(f"  skip: could not click {follow_label} ({exc})")
                    return []
                follows += 1
                saw_response_at = None
                continue
        page.wait_for_timeout(300)

    print(f"  skip {label}: no file arrived")
    return []


def scrape_page(
    page,
    context,
    url: str,
    output_dir: Path,
    downloads: list,
    file_responses: list,
    popups: list,
    used: set[Path],
    timeout_s: float,
) -> list[Path]:
    print(f"\n{url}")
    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    try:
        page.wait_for_function(
            """() => [...document.querySelectorAll('a, button')].some((el) =>
              /download|export|\\.csv|\\bcsv\\b/i.test(
                `${el.innerText || ''} ${el.getAttribute('aria-label') || ''} ${el.href || ''}`
              ))""",
            timeout=30_000,
        )
    except Exception:
        print("  no download control found")
        return []
    _dismiss_cookies(page)
    page.wait_for_timeout(500)

    controls = _scan(page)
    if not controls:
        print("  no download control found")
        return []

    slug = site_slug(url)
    known = {control["key"] for control in controls}
    saved: list[Path] = []
    for control in controls:
        kind = classify_control(control.get("href") or "", page.url)
        label = _label(control)
        if kind == "form":
            print(f"  skip {label}: form {control.get('href')}")
            continue
        if kind == "href":
            target = actionable_href(control.get("href") or "", page.url)
            print(f"  open {label}")
            path = _download_href(context, target, page.url, slug, output_dir, used)
            if path is not None:
                saved.append(path)
            continue
        saved.extend(
            _trigger_button(
                page,
                context,
                control,
                known,
                downloads,
                file_responses,
                popups,
                slug,
                output_dir,
                used,
                timeout_s,
            )
        )
    return saved


def scrape(urls: list[str], output_dir: Path, headed: bool, timeout_s: float) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    browser_urls: list[str] = []
    for url in urls:
        if is_climate_laws_search(url):
            try:
                saved.extend(download_climate_laws(url, output_dir))
            except Exception as exc:
                print(f"  failed: {exc}", file=sys.stderr)
        else:
            browser_urls.append(url)
    if not browser_urls:
        return saved

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "Playwright is not installed. Run: pip install playwright && python -m playwright install chromium",
            file=sys.stderr,
        )
        return saved

    downloads: list = []
    file_responses: list = []
    popups: list = []
    used: set[Path] = set()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        context = browser.new_context(
            accept_downloads=True,
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        page = context.new_page()

        def on_response(response) -> None:
            headers = dict(response.headers)
            if response.ok and is_file_response(headers, response.url):
                file_responses.append(response)

        context.on("download", lambda download: downloads.append(download))
        context.on("response", on_response)
        context.on("page", lambda new_page: popups.append(new_page))

        for url in browser_urls:
            try:
                saved.extend(
                    scrape_page(
                        page,
                        context,
                        url,
                        output_dir,
                        downloads,
                        file_responses,
                        popups,
                        used,
                        timeout_s,
                    )
                )
            except Exception as exc:
                print(f"  failed: {exc}", file=sys.stderr)
        browser.close()
    return saved


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download files from policy-database pages.")
    parser.add_argument(
        "--url",
        action="append",
        dest="urls",
        help="Page to scrape. Repeat to pass several. Defaults to Climate Laws and the IEA policies database.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for the downloaded files (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120,
        help="Seconds to wait for a button to produce a file (default: 120).",
    )
    parser.add_argument("--headed", action="store_true", help="Show the browser window.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    urls = args.urls or list(DEFAULT_URLS)
    saved = scrape(urls, args.output_dir, args.headed, args.timeout)
    print()
    if not saved:
        print("No files downloaded.")
        return 1
    print(f"Saved {len(saved)} file(s) in {args.output_dir}:")
    for path in saved:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
