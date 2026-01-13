import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from verify_required_fields import collect_form_labels


def run_manual_check(url: str, headless: bool = True, output_path: Optional[Path] = None):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        page = browser.new_page()
        try:
            page.set_extra_http_headers({
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            })

            print(f"Opening {url} ...")
            page.goto(url, timeout=15000, wait_until="domcontentloaded")
            time.sleep(1.5)

            labels, linkedin_required = collect_form_labels(page)

            print("\nDetected field labels:")
            for label in labels:
                print(f"- {label}")

            print(f"\nLinkedIn required: {linkedin_required}")

            mongo_payload = {
                "input_field_labels": labels,
                "linkedin_required": linkedin_required,
                "required_fields_checked_at": datetime.utcnow().isoformat()
            }

            print("\nMongoDB payload preview:")
            print("-" * 60)
            print(json.dumps(mongo_payload, indent=2))

            if output_path:
                payload_text = "\n".join([
                    "Input Field Labels:",
                    *[f"- {label}" for label in labels],
                    f"\nLinkedIn required: {linkedin_required}",
                    "\nMongoDB payload:",
                    json.dumps(mongo_payload, indent=2)
                ])
                output_path.write_text(payload_text, encoding="utf-8")
                print(f"\nResults written to {output_path}")

        except PlaywrightTimeoutError:
            print("❌ Timeout while loading the page.")
        except Exception as exc:
            print(f"❌ Error: {exc}")
        finally:
            browser.close()


def main():
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = input("Enter job application URL: ").strip()

    headless_choice = input("Run headless? (Y/n): ").strip().lower()
    headless = False if headless_choice == "n" else True

    output_choice = input("Save results to file? (y/N): ").strip().lower()
    output_path = None
    if output_choice == "y":
        filename = input("Enter output filename (default manual_required_fields.txt): ").strip() or "manual_required_fields.txt"
        output_path = Path(filename)

    run_manual_check(url, headless=headless, output_path=output_path)


if __name__ == "__main__":
    main()

