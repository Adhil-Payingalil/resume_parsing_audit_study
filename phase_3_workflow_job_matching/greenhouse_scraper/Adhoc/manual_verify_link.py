"""
Utility script to manually verify a single job link using the existing
`verify_job_links.JobLinkVerifier` logic.
"""

import argparse
import sys
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

from verify_job_links import HEADLESS, JobLinkVerifier


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manually verify a single job link using Playwright."
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="Job URL to verify. If omitted, an interactive prompt will ask for it.",
    )
    parser.add_argument(
        "--headless",
        dest="headless",
        action="store_true",
        help="Force headless mode on.",
    )
    parser.add_argument(
        "--no-headless",
        dest="headless",
        action="store_false",
        help="Force headless mode off.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print additional diagnostics, including a snippet of page text.",
    )
    parser.set_defaults(headless=None)
    return parser.parse_args()


def _extract_greenhouse_job_id(job_url: str) -> str | None:
    """Return the Greenhouse job id (gh_jid) from the URL if present."""
    try:
        query = parse_qs(urlparse(job_url).query)
        job_id = query.get("gh_jid", [None])[0]
        if job_id:
            return job_id.strip()
    except Exception:  # pylint: disable=broad-except
        pass
    return None


def _evaluate_greenhouse_signals(page, job_url: str, page_text: str | None) -> dict:
    """
    Check for signals that a Greenhouse job is actually rendered on the page.

    Returns a dictionary with booleans and an experimental status suggestion.
    """
    info: dict[str, object] = {}
    job_id = _extract_greenhouse_job_id(job_url)
    info["gh_jid"] = job_id

    body_text = page_text or ""
    lower_body = body_text.lower()

    try:
        html = page.content()
    except Exception:  # pylint: disable=broad-except
        html = ""

    iframe_src = None
    iframe_body_text = ""
    try:
        iframe = page.query_selector('iframe[src*="greenhouse.io"]')
        if iframe:
            info["has_greenhouse_iframe"] = True
            try:
                iframe_src = iframe.get_attribute("src")
            except Exception:  # pylint: disable=broad-except
                iframe_src = "[unavailable]"
        else:
            info["has_greenhouse_iframe"] = False
    except Exception:  # pylint: disable=broad-except
        info["has_greenhouse_iframe"] = False

    info["greenhouse_iframe_src"] = iframe_src

    try:
        grnhse_container = page.query_selector("#grnhse_app")
        info["has_grnhse_app"] = bool(grnhse_container)
    except Exception:  # pylint: disable=broad-except
        info["has_grnhse_app"] = False

    job_id_present = False
    if job_id:
        job_id_present = job_id in lower_body or job_id in html
    info["job_id_present"] = job_id_present

    iframe_job_id_present = False
    iframe_has_apply_text = False
    iframe_content_length = 0

    if iframe:
        try:
            frame = next((f for f in page.frames if f == iframe.content_frame()), None)
        except Exception:  # pylint: disable=broad-except
            frame = None

        if frame:
            try:
                iframe_body_text = frame.inner_text("body")
                iframe_content_length = len(iframe_body_text)
                iframe_lower = iframe_body_text.lower()
                iframe_has_apply_text = "apply" in iframe_lower or "submit application" in iframe_lower
                if job_id:
                    iframe_job_id_present = job_id in iframe_lower
            except Exception as exc:  # pylint: disable=broad-except
                iframe_body_text = f"[Failed to read iframe body: {exc}]"

    info["iframe_job_id_present"] = iframe_job_id_present
    info["iframe_has_apply_text"] = iframe_has_apply_text
    info["iframe_content_length"] = iframe_content_length

    has_signals = info["has_greenhouse_iframe"] and (
        iframe_job_id_present
        or iframe_has_apply_text
        or iframe_content_length > 400
    )

    info["experimental_status"] = "active" if has_signals else "inactive"
    info["iframe_body_preview"] = (
        iframe_body_text[:200] + ("..." if len(iframe_body_text) > 200 else "")
        if isinstance(iframe_body_text, str)
        else iframe_body_text
    )
    return info


def verify_single_link(job_url: str, headless: bool, debug: bool = False):
    """Run the job link check for a single URL."""
    verifier = JobLinkVerifier()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        page = browser.new_page()
        page.set_extra_http_headers(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }
        )

        page_text: str | None = None
        greenhouse_info: dict[str, object] = {}

        try:
            job_id, status, final_url, reason = verifier.check_job_link(
                page, job_url, "manual-test"
            )
            if debug:
                try:
                    page_text = page.inner_text("body")
                except Exception as exc:  # pylint: disable=broad-except
                    page_text = f"[Failed to read body text: {exc}]"
            greenhouse_info = _evaluate_greenhouse_signals(
                page, job_url, page_text if isinstance(page_text, str) else None
            )
            debug_info = {}
            if debug:
                try:
                    debug_info["title"] = page.title()
                except Exception:
                    debug_info["title"] = "[unavailable]"

                debug_info["found_apply_selector"] = status == "active"
                debug_info["page_text_length"] = len(page_text) if page_text else 0

                try:
                    debug_info["has_apply_text"] = "apply" in (page_text or "").lower()
                except Exception:
                    debug_info["has_apply_text"] = False
                debug_info["greenhouse_signals"] = greenhouse_info
            return (
                status,
                final_url or job_url,
                reason,
                page_text,
                greenhouse_info,
                debug_info,
            )
        finally:
            page.close()
            browser.close()


def main():
    """Prompt the user for a URL and display the verification result."""
    args = parse_args()

    if args.url:
        job_url = args.url.strip()
    else:
        job_url = input("Enter the job URL to verify: ").strip()

    if not job_url:
        print("No URL provided. Exiting.")
        sys.exit(1)

    headless = HEADLESS if args.headless is None else args.headless

    try:
        (
            base_status,
            final_url,
            reason,
            page_text,
            greenhouse_info,
            debug_info,
        ) = verify_single_link(
            job_url, headless=headless, debug=args.debug
        )
    except Exception as exc:
        print(f"Error verifying link: {exc}")
        sys.exit(1)

    final_status = base_status
    final_reason = reason
    experimental_status = greenhouse_info.get("experimental_status")
    if base_status == "active" and experimental_status == "inactive":
        final_status = "inactive"
        if not final_reason:
            final_reason = "Greenhouse content not detected"

    print("\nVerification Result")
    print("-" * 60)
    print(f"Status     : {final_status}")
    if final_status != base_status:
        print(f"(Original) : {base_status}")
    print(f"Final URL  : {final_url}")
    if final_reason:
        print(f"Reason     : {final_reason}")
    else:
        print("Reason     : (none)")

    if args.debug:
        print("\nPage text preview (first 500 chars):")
        print("-" * 60)
        snippet = (page_text or "").strip()
        if snippet:
            print(snippet[:500])
            if len(snippet) > 500:
                print("... [truncated]")
        else:
            print("(empty)")

        if debug_info:
            print("\nDebug info:")
            for key, value in debug_info.items():
                if isinstance(value, dict):
                    print(f"  {key}:")
                    for sub_key, sub_value in value.items():
                        print(f"    {sub_key}: {sub_value}")
                else:
                    print(f"  {key}: {value}")


if __name__ == "__main__":
    main()


