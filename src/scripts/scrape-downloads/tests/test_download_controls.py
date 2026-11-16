"""Tests for download-control classification (no browser, no internet).

Run from the repository root:
    python -m pytest src/scripts/scrape-downloads/tests -q
"""

from pathlib import Path

from download_controls import (
    actionable_href,
    allocate_path,
    build_search_body,
    category_slug,
    classify_control,
    filename_for_response,
    filename_from_content_disposition,
    html_is_form_gate,
    is_climate_laws_search,
    is_download_candidate,
    is_file_response,
    is_form_url,
    merge_csv_files,
    safe_filename,
    site_slug,
)

CLIMATE = "https://climate-laws.org/search?c=policies"
IEA = "https://www.iea.org/policies"


def test_climate_laws_keeps_the_search_button_and_skips_jotform():
    assert is_download_candidate("this search", "Download search results as CSV", "", "download-search-csv")
    assert classify_control("", CLIMATE) == "button"

    whole_database = "https://form.jotform.com/233131638610347"
    assert is_download_candidate("whole database", "", whole_database, "download-entire-search-csv")
    assert classify_control(whole_database, CLIMATE) == "form"

    alerts = "https://form.jotform.com/252034552030341"
    assert is_download_candidate("Email alerts", "", alerts, "download-entire-search-csv")
    assert classify_control(alerts, CLIMATE) == "form"


def test_iea_download_is_a_direct_file_and_the_nav_card_is_not_a_candidate():
    csv_url = "https://api.iea.org/v3/policies?csv=true"
    assert is_download_candidate("Download", "", csv_url, "")
    assert classify_control(csv_url, IEA) == "href"
    assert actionable_href(csv_url, IEA) == csv_url

    nav_text = (
        "Data sets\n"
        "Free and paid data sets from across the energy system available for download"
    )
    assert not is_download_candidate(
        nav_text, "", "https://www.iea.org/data-and-statistics/data-sets", ""
    )


def test_form_pages_are_detected_from_the_url_or_the_html():
    assert is_form_url("https://form.jotform.com/233131638610347")
    assert is_form_url("https://docs.google.com/forms/d/e/abc/viewform")
    assert not is_form_url("https://api.iea.org/v3/policies?csv=true")
    assert html_is_form_gate('<form><input type="email" name="email"></form>')
    assert not html_is_form_gate("<p>Please read our terms of use.</p><button>Download</button>")


def test_file_headers_and_iea_filename():
    headers = {
        "content-type": "text/csv",
        "content-disposition": 'attachment; filename="IEA_PAMS_Export 11/14/2026, 8:08:55 AM.csv"',
    }
    assert is_file_response(headers, "https://api.iea.org/v3/policies?csv=true")
    assert not is_file_response({"content-type": "application/json"}, "https://example.org/api")
    raw = filename_from_content_disposition(headers["content-disposition"])
    assert raw == "IEA_PAMS_Export 11/14/2026, 8:08:55 AM.csv"
    assert "/" not in safe_filename(raw)
    name = filename_for_response(headers, "https://api.iea.org/v3/policies?csv=true", site_slug(IEA))
    assert name.startswith("iea__")
    assert name.endswith(".csv")
    assert "/" not in name


THEME = {
    "deprecatedCategories": {
        "options": [
            {"label": "All", "slug": "All", "value": ["CORPUS-ALL"]},
            {
                "label": "Policies",
                "slug": "policies",
                "value": ["CORPUS-POLICIES"],
                "category": ["Executive"],
            },
        ]
    }
}


def test_climate_laws_search_body_uses_the_category_and_continuation_token():
    assert is_climate_laws_search(CLIMATE)
    assert not is_climate_laws_search(IEA)
    assert category_slug(CLIMATE) == "policies"
    assert category_slug("https://climate-laws.org/search") == "All"
    body = build_search_body(THEME, "policies", ["next-page"], page_size=500, year_range=("1947", "2027"))
    assert body["corpus_import_ids"] == ["CORPUS-POLICIES"]
    assert body["keyword_filters"]["categories"] == ["Executive"]
    assert body["continuation_tokens"] == ["next-page"]
    assert body["page_size"] == 500
    assert body["offset"] == 0


def test_merge_csv_files_keeps_one_copy_of_overlapping_pages(tmp_path: Path):
    first = tmp_path / "o-0.csv"
    second = tmp_path / "o-20.csv"
    first.write_text("name,year\nAlpha,2020\nBeta,2021\n", encoding="utf-8")
    second.write_text("name,year\nBeta,2021\nGamma,2022\n", encoding="utf-8")
    dest = tmp_path / "merged.csv"
    assert merge_csv_files([first, second], dest) == 3
    assert dest.read_text(encoding="utf-8").splitlines() == [
        "name,year",
        "Alpha,2020",
        "Beta,2021",
        "Gamma,2022",
    ]


def test_allocate_path_suffixes_names_reused_in_one_run(tmp_path: Path):
    used: set[Path] = set()
    first = allocate_path(tmp_path, "iea__policies.csv", used)
    second = allocate_path(tmp_path, "iea__policies.csv", used)
    assert first.name == "iea__policies.csv"
    assert second.name == "iea__policies-2.csv"
