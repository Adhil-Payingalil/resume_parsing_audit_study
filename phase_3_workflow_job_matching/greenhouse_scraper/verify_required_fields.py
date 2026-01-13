import os
import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bson import ObjectId
import logging

# ... imports ...
from config import MONGODB_URI, MONGODB_DATABASE, MONGODB_COLLECTION, DEFAULT_VERIFICATION_FILTER
import logging

# Load environment variables
load_dotenv()

# Ensure logs directory exists
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(logs_dir / "verify_required_fields.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Browser settings
HEADLESS = True
TIMEOUT = 15000  # ms
MAX_RETRIES = 2

# Unsupported input field patterns configuration
UNSUPPORTED_INPUT_FIELD_PATTERNS = [
    "linkedin",
    "portfolio link",
    "portfolio password",
    "street address",
    "postal code/zip code",
    "video",
    "cover letter"
]


def collect_form_labels(page, unsupported_patterns: List[str]) -> Tuple[List[str], bool, List[str]]:
    """
    Collect visible form labels from the current page and detect unsupported fields.

    Args:
        page: Playwright page object
        unsupported_patterns: List of patterns to match against field labels

    Returns:
        Tuple of (all labels list, unsupported_input_fields flag, unsupported field labels list)
    """
    # Convert patterns to JavaScript array for injection
    patterns_js = json.dumps(unsupported_patterns)
    
    script = f"""
    () => {{
        const unsupportedPatterns = {patterns_js};
        
        const sanitize = (text) => {{
            if (!text) return '';
            return text.replace(/\\s+/g, ' ').trim();
        }};

        const fields = [];
        const seen = new Set();

        const gatherLabel = (labelEl) => {{
            if (!labelEl) return;
            const text = sanitize(labelEl.innerText || labelEl.textContent);
            if (!text) return;

            // Skip helper markers like '* indicates a required field'
            const lower = text.toLowerCase();
            if (lower.includes('indicates a required field')) return;

            if (!seen.has(text)) {{
                seen.add(text);
                fields.push(text);
            }}
        }};

        const forms = document.querySelectorAll('form');
        forms.forEach(form => {{
            const labels = form.querySelectorAll('label');
            labels.forEach(labelEl => {{
                // Only consider labels that are associated with controls
                if (labelEl.htmlFor) {{
                    const control = form.querySelector(`#${{CSS.escape(labelEl.htmlFor)}}`);
                    if (control) {{
                        gatherLabel(labelEl);
                        return;
                    }}
                }}
                if (labelEl.querySelector('input, textarea, select')) {{
                    gatherLabel(labelEl);
                    return;
                }}
                const control = labelEl.closest('label')?.querySelector('input, textarea, select');
                if (control) {{
                    gatherLabel(labelEl);
                }}
            }});

            const legends = form.querySelectorAll('fieldset legend');
            legends.forEach(legendEl => gatherLabel(legendEl));
        }});

        // Fallback: look for elements commonly used as field labels in Greenhouse templates
        const fieldSelectors = [
            '.application-field label',
            '.application-question label',
            '.field label',
            '.fields label',
            '.application-field .label',
            '.application-field .field-label',
            '.application-question .question-label'
        ];

        fieldSelectors.forEach(selector => {{
            const candidates = document.querySelectorAll(selector);
            candidates.forEach(el => gatherLabel(el));
        }});

        // Check for unsupported fields: must match pattern AND be required (*)
        const unsupportedFields = [];
        fields.forEach(label => {{
            const lower = label.toLowerCase();
            const isRequired = label.includes('*');
            
            if (isRequired) {{
                for (const pattern of unsupportedPatterns) {{
                    if (lower.includes(pattern.toLowerCase())) {{
                        unsupportedFields.push(label);
                        break;
                    }}
                }}
            }}
        }});

        const hasUnsupportedFields = unsupportedFields.length > 0;

        return {{ fields, hasUnsupportedFields, unsupportedFields }};
    }}
    """

    result = page.evaluate(script)
    fields = result.get("fields", []) if isinstance(result, dict) else []
    unsupported_input_fields = result.get("hasUnsupportedFields", False) if isinstance(result, dict) else False
    unsupported_field_labels = result.get("unsupportedFields", []) if isinstance(result, dict) else []
    return fields, unsupported_input_fields, unsupported_field_labels


def check_unsupported_fields_from_labels(
    labels: List[str], 
    unsupported_patterns: List[str]
) -> Tuple[bool, List[str]]:
    """
    Check existing labels for unsupported field patterns.
    
    Args:
        labels: List of existing field labels
        unsupported_patterns: List of patterns to match against field labels
    
    Returns:
        Tuple of (unsupported_input_fields flag, unsupported field labels list)
    """
    unsupported_field_labels = []
    
    for label in labels:
        if not label or not isinstance(label, str):
            continue
        
        # Only check required fields (containing *)
        if '*' not in label:
            continue
        
        label_lower = label.lower()
        for pattern in unsupported_patterns:
            if pattern.lower() in label_lower:
                unsupported_field_labels.append(label)
                break  # Found a match, no need to check other patterns for this label
    
    unsupported_input_fields = len(unsupported_field_labels) > 0
    return unsupported_input_fields, unsupported_field_labels

class RequiredFieldChecker:
    def __init__(self, cycle: float = 0):
        self.mongo_client: Optional[MongoClient] = None
        self.collection = None
        self.results: List[Dict[str, Any]] = []
        self.processed_count = 0
        self.error_count = 0
        self.unsupported_input_fields_count = 0
        self.total_jobs_considered = 0
        self.jobs_using_existing_labels = 0
        self.jobs_scraped = 0
        
        self.cycle = cycle
        self.job_filter = DEFAULT_VERIFICATION_FILTER.copy()
        self.job_filter['cycle'] = self.cycle

    def setup_mongodb_connection(self):
        if not MONGODB_URI:
            raise RuntimeError("MONGODB_URI not found in environment variables")

        try:
            self.mongo_client = MongoClient(MONGODB_URI)
            self.mongo_client.admin.command("ping")
            db = self.mongo_client[MONGODB_DATABASE]
            self.collection = db[MONGODB_COLLECTION]
            logger.info(f"✅ Connected to MongoDB: {MONGODB_DATABASE}.{MONGODB_COLLECTION}")
        except ConnectionFailure as exc:
            raise RuntimeError(f"Failed to connect to MongoDB: {exc}") from exc

    def build_query(self, base_criteria: Dict) -> Dict:
        """Combine specific criteria with the job filter (cycle, etc.)"""
        return {
            '$and': [
                self.job_filter,
                base_criteria
            ]
        }

    def get_jobs_to_process(
        self,
        limit: Optional[int] = None,
        skip_processed: bool = True
    ) -> List[Dict[str, Any]]:

        # Base criteria for verification (must have a link)
        base_criteria = {"job_link": {"$exists": True, "$ne": ""}}
        
        # Build the full query with cycle filter
        query = self.build_query(base_criteria)

        if skip_processed:
            # Add OR condition for missing data to the existing AND query
            # We need to act on the specific criteria part
            or_condition = {
                "$or": [
                    {"input_field_labels": {"$exists": False}},
                    {
                        "input_field_labels": {"$exists": True},
                        "$or": [
                            {"unsupported_input_fields": {"$exists": False}},
                            {"unsupported_input_field_labels": {"$exists": False}}
                        ]
                    }
                ]
            }
            # Append to the $and list
            query['$and'].append(or_condition)

        projection = {
            "_id": 1,
            "job_link": 1,
            "title": 1,
            "company": 1,
            "input_field_labels": 1
        }

        try:
            cursor = self.collection.find(query, projection).sort("created_at", -1)
            if limit:
                cursor = cursor.limit(limit)

            jobs = list(cursor)
            jobs_with_existing_labels = sum(1 for job in jobs if job.get("input_field_labels"))
            jobs_needing_scrape = len(jobs) - jobs_with_existing_labels
            
            logger.info(
                "Found %s jobs to process for Cycle %s (limit=%s, skip_processed=%s)",
                len(jobs),
                self.cycle,
                limit if limit else "all",
                skip_processed
            )
            # ... logging ...
            self.total_jobs_considered = len(jobs)
            return jobs
        except Exception as e:
            logger.error(f"Error finding jobs: {e}")
            return []

    def process_job(self, job: Dict[str, Any], browser) -> Optional[Dict[str, Any]]:
        job_id = str(job["_id"])
        job_url = job.get("job_link")
        job_title = job.get("title", "Unknown")
        company = job.get("company", "Unknown")
        existing_labels = job.get("input_field_labels")

        logger.info(f"Processing job {job_id}: {job_title} at {company}")

        if not job_url:
            logger.warning(f"Job {job_id} has no job_link; skipping")
            return None

        # If input_field_labels already exists, use them without scraping
        if existing_labels and isinstance(existing_labels, list):
            self.jobs_using_existing_labels += 1
            logger.info(
                f"Using existing input_field_labels for job {job_id} "
                f"({len(existing_labels)} labels found, skipping scrape)"
            )
            unsupported_input_fields, unsupported_field_labels = check_unsupported_fields_from_labels(
                existing_labels, UNSUPPORTED_INPUT_FIELD_PATTERNS
            )
            result = {
                "job_id": job_id,
                "job_title": job_title,
                "company": company,
                "job_link": job_url,
                "input_field_labels": existing_labels,
                "unsupported_input_fields": unsupported_input_fields,
                "unsupported_input_field_labels": unsupported_field_labels,
                "checked_at": datetime.utcnow().isoformat()
            }
            logger.info(
                f"Checked existing labels for job {job_id} "
                f"(Unsupported fields: {unsupported_input_fields}, "
                f"Count: {len(unsupported_field_labels)})"
            )
            return result

        # No existing labels, need to scrape
        self.jobs_scraped += 1
        logger.info(f"Scraping input_field_labels for job {job_id} (no existing labels found)")
        for attempt in range(1, MAX_RETRIES + 1):
            page = browser.new_page()
            try:
                page.set_extra_http_headers({
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                })
                logger.debug(f"Navigating to {job_url} (attempt {attempt}/{MAX_RETRIES})")
                page.goto(job_url, timeout=TIMEOUT, wait_until="domcontentloaded")
                time.sleep(1.5)

                labels, unsupported_input_fields, unsupported_field_labels = collect_form_labels(
                    page, UNSUPPORTED_INPUT_FIELD_PATTERNS
                )
                result = {
                    "job_id": job_id,
                    "job_title": job_title,
                    "company": company,
                    "job_link": job_url,
                    "input_field_labels": labels,
                    "unsupported_input_fields": unsupported_input_fields,
                    "unsupported_input_field_labels": unsupported_field_labels,
                    "checked_at": datetime.utcnow().isoformat()
                }

                logger.info(
                    f"Collected {len(labels)} labels for job {job_id} "
                    f"(Unsupported fields: {unsupported_input_fields}, "
                    f"Count: {len(unsupported_field_labels)})"
                )
                return result

            except PlaywrightTimeoutError:
                logger.warning(f"Timeout loading {job_url} for job {job_id} (attempt {attempt})")
                if attempt == MAX_RETRIES:
                    self.error_count += 1
            except Exception as exc:
                logger.error(f"Error processing job {job_id}: {exc}")
                if attempt == MAX_RETRIES:
                    self.error_count += 1
            finally:
                try:
                    page.close()
                except Exception:
                    pass

            time.sleep(1)

        return None

    def update_job_document(
        self, 
        job_id: str, 
        labels: List[str], 
        unsupported_input_fields: bool,
        unsupported_field_labels: List[str]
    ):
        update_data = {
            "input_field_labels": labels,
            "unsupported_input_fields": unsupported_input_fields,
            "unsupported_input_field_labels": unsupported_field_labels,
            "required_fields_checked_at": datetime.utcnow()
        }
        result = self.collection.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": update_data}
        )
        if result.modified_count > 0:
            logger.debug(f"Updated job {job_id} with required field data")
        else:
            logger.warning(f"No MongoDB changes made for job {job_id}")

    def save_results_to_json(self, filename: Optional[str] = None) -> Optional[str]:
        if not self.results:
            logger.info("No results to save")
            return None

        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)

        if not filename:
            filename = f"required_fields_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

        filepath = data_dir / filename
        with open(filepath, "w", encoding="utf-8") as json_file:
            json.dump(self.results, json_file, indent=2)

        logger.info(f"Results saved to {filepath}")
        return str(filepath)
   
    def run(self, limit: Optional[int] = None, skip_processed: bool = True):
        start_time = time.time()
        self.setup_mongodb_connection()
        
        # Diagnostic print
        total_cycle_jobs = self.collection.count_documents(self.job_filter)
        print(f"📊 Diagnostic: Found {total_cycle_jobs} total jobs for Cycle {self.cycle}")
        
        jobs = self.get_jobs_to_process(limit=limit, skip_processed=skip_processed)
        
        if not jobs:
            logger.info("No jobs to process")
            return

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=HEADLESS)
            try:
                for index, job in enumerate(jobs, start=1):
                    result = self.process_job(job, browser)
                    if result:
                        self.processed_count += 1
                        self.results.append(result)
                        try:
                            self.update_job_document(
                                result["job_id"],
                                result["input_field_labels"],
                                result["unsupported_input_fields"],
                                result["unsupported_input_field_labels"]
                            )
                        except Exception as exc:
                            logger.error(
                                "Failed to update MongoDB for job %s: %s",
                                result["job_id"],
                                exc
                            )
                            self.error_count += 1
                        if result["unsupported_input_fields"]:
                            self.unsupported_input_fields_count += 1
                    
                    if index < len(jobs):
                        time.sleep(1)
            finally:
                browser.close()
        
        # ... stats logging ...
        duration = time.time() - start_time
        logger.info("=" * 60)
        logger.info(f"✅ Required field extraction completed for Cycle {self.cycle}")
        # ... rest of logging ...
        self.save_results_to_json()
        if self.mongo_client:
            self.mongo_client.close()

def main():
    print("Required Field Checker")
    print("=" * 60)
    
    # Get cycle input
    default_cycle = DEFAULT_VERIFICATION_FILTER.get('cycle', 0)
    print(f"\nDefault Cycle Number: {default_cycle}")
    cycle_input = input(f"Enter Cycle Number (default {default_cycle}): ").strip()
    
    try:
        cycle = float(cycle_input) if cycle_input else default_cycle
        if cycle.is_integer():
             cycle = int(cycle)
    except ValueError:
        print(f"Invalid input. Using default cycle: {default_cycle}")
        cycle = default_cycle
        
    print(f"Using Cycle Number: {cycle}")

    checker = RequiredFieldChecker(cycle=cycle)

    print("This script extracts form field labels and detects unsupported input fields.")
    print(f"Unsupported field patterns: {', '.join(UNSUPPORTED_INPUT_FIELD_PATTERNS)}")
    
    try:
        checker.setup_mongodb_connection()
        
        # Pre-check counts
        total_cycle_jobs = checker.collection.count_documents(checker.job_filter)
        print(f"\nDiagnostic: Total jobs for Cycle {checker.cycle}: {total_cycle_jobs}")

        skip_processed = True
        
        # Check if we have work to do
        jobs = checker.get_jobs_to_process(limit=1, skip_processed=True)
        if not jobs:
            choice = input(f"All jobs for Cycle {cycle} seem processed. Reprocess ALL? (y/N): ").strip().lower()
            skip_processed = False if choice == "y" else True

        limit_input = input("Enter number of jobs to process (Enter for all): ").strip()
        limit = int(limit_input) if limit_input else None

        headless_choice = input("Run in headless mode? (Y/n): ").strip().lower()
        if headless_choice == "n":
            global HEADLESS
            HEADLESS = False

        print("\nStarting extraction...")
        checker.run(limit=limit, skip_processed=skip_processed)

    except KeyboardInterrupt:
        logger.info("Extraction interrupted by user")
    except Exception as exc:
        logger.error(f"Extraction failed: {exc}")
        raise

if __name__ == "__main__":
    main()

