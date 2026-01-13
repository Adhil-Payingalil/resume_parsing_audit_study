import os
import time
import csv
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bson import ObjectId
import logging

# Load environment variables
load_dotenv()

# Create logs directory if it doesn't exist
logs_dir = Path('logs')
logs_dir.mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(logs_dir / 'verify_job_links.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "Resume_study")
MONGODB_COLLECTION = "Job_postings_greenhouse"

# Browser settings
HEADLESS = True  # Set to False to see the browser
TIMEOUT = 15000  # 15 seconds timeout
MAX_RETRIES = 2

# Common phrases that indicate a job is no longer available
JOB_CLOSED_INDICATORS = [
    "no longer accepting applications",
    "Current openings",
    "position has been filled",
    "job is no longer available",
    "this job posting is no longer active",
    "posting has expired",
    "application window has closed",
    "no longer open",
    "position is closed",
    "posting is closed",
    "this position has been filled",
    "we are no longer accepting applications",
    "job posting has expired",
    "this job is closed",
    "applications closed",
    "role has been filled",
    "position filled",
    "sorry, this job is no longer available",
    "this job has been closed",
    "job no longer exists",
    "the job you are looking for",
    "could not be found",
    "404",
    "page not found",
    "not found"
]

class JobLinkVerifier:
    def __init__(self):
        self.mongo_client = None
        self.collection = None
        self.start_time = None
        self.verified_count = 0
        self.active_count = 0
        self.inactive_count = 0
        self.error_count = 0
        self.results = []
        
    def setup_mongodb_connection(self):
        """Set up MongoDB connection"""
        if not MONGODB_URI:
            raise Exception("MONGODB_URI not found in environment variables")
        
        try:
            self.mongo_client = MongoClient(MONGODB_URI)
            # Test the connection
            self.mongo_client.admin.command('ping')
            db = self.mongo_client[MONGODB_DATABASE]
            self.collection = db[MONGODB_COLLECTION]
            
            logger.info(f"✅ Connected to MongoDB: {MONGODB_DATABASE}.{MONGODB_COLLECTION}")
            return True
        except ConnectionFailure as e:
            raise Exception(f"Failed to connect to MongoDB: {e}")
        except Exception as e:
            raise Exception(f"MongoDB setup error: {e}")
    
    def get_jobs_to_verify(self, limit: Optional[int] = None, skip_verified: bool = True, 
                           include_active: bool = False) -> List[Dict]:
        """
        Get jobs from MongoDB that need link verification
        
        Args:
            limit: Maximum number of jobs to verify (None for all)
            skip_verified: If True, skip jobs that already have link_status field
            include_active: If True, also include jobs with link_status='active' for re-verification
            
        Returns:
            List of job documents
        """
        # Build base filter with all required conditions
        base_filter = {
            'job_link': {'$exists': True, '$ne': ''},
            'jd_extraction': True,
            'link_type': 'greenhouse',
            'cycle': 4
        }
        
        # Start with base filter
        query = dict(base_filter)
        
        # Skip already verified jobs if requested
        if skip_verified:
            if include_active:
                # Include both unverified jobs AND jobs marked as active
                query = {
                    **base_filter,  # Preserve all base filter conditions including cycle
                    '$or': [
                        {'link_status': {'$exists': False}},
                        {'link_status': 'active'}
                    ]
                }
            else:
                # Only unverified jobs - can keep simple structure
                query['link_status'] = {'$exists': False}
        
        # Log the actual query being executed for debugging
        logger.info(f"MongoDB query being executed: {query}")
        
        cursor = self.collection.find(query, {
            '_id': 1, 
            'job_link': 1, 
            'title': 1, 
            'company': 1,
            'created_at': 1,
            'link_status': 1,
            'link_verified_at': 1
        }).sort('created_at', -1)
        
        if limit:
            jobs = list(cursor.limit(limit))
        else:
            jobs = list(cursor)
        
        total_count = self.collection.count_documents(base_filter)
        logger.info(f"Found {len(jobs)} jobs to verify (out of {total_count} total jobs with links)")
        
        return jobs
    
    def check_job_link(self, page, job_url: str, job_id: str) -> Tuple[str, str, Optional[str], Optional[str]]:
        """
        Check if a job link is still active
        
        Args:
            page: Playwright page
            job_url: The job posting URL
            job_id: MongoDB document ID for logging
            
        Returns:
            Tuple of (job_id, status, final_url, reason)
            status can be: 'active', 'inactive', 'error', 'redirect'
        """
        if not job_url or not job_url.startswith('http'):
            error_msg = f"Invalid URL format"
            logger.warning(f"Invalid URL for job {job_id}: {job_url}")
            return job_id, 'error', None, error_msg
        
        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"Checking job {job_id} (attempt {attempt + 1}/{MAX_RETRIES}): {job_url}")
                
                # Navigate to the job URL
                response = page.goto(job_url, timeout=TIMEOUT, wait_until='domcontentloaded')
                
                # Get the final URL after any redirects
                final_url = page.url
                
                # Wait a bit for any dynamic content
                time.sleep(2)
                
                # Check response status
                if response and response.status >= 400:
                    logger.info(f"❌ Job {job_id} returned status {response.status}")
                    return job_id, 'inactive', final_url, f"HTTP Status: {response.status}"
                
                # Check if URL redirected significantly
                original_path = job_url.split('/')[-1] if '/' in job_url else job_url
                final_path = final_url.split('/')[-1] if '/' in final_url else final_url
                
                # If redirected to a different page (not just protocol or trailing slash changes)
                if original_path != final_path and not final_url.startswith(job_url.rstrip('/')):
                    # Check if it's redirected to homepage or careers page
                    if any(keyword in final_url.lower() for keyword in ['/jobs', '/careers', '/about', 'greenhouse.io']):
                        if final_url.count('/') <= 3:  # Likely a homepage or generic careers page
                            logger.info(f"🔀 Job {job_id} redirected to: {final_url}")
                            return job_id, 'inactive', final_url, f"Redirected to generic page"
                
                # Get page content
                page_text = page.inner_text('body').lower()
                
                # Check for job closed indicators
                for indicator in JOB_CLOSED_INDICATORS:
                    if indicator.lower() in page_text:
                        logger.info(f"❌ Job {job_id} is closed (found: '{indicator}')")
                        return job_id, 'inactive', final_url, f"Found indicator: {indicator}"
                
                # Check if the page has typical job posting elements
                has_apply_button = False
                try:
                    # Look for apply button or similar elements
                    apply_selectors = [
                        'text="apply"',
                        'text="apply now"',
                        'text="submit application"',
                        '[class*="apply"]',
                        'button[class*="apply"]',
                        'a[class*="apply"]'
                    ]
                    
                    for selector in apply_selectors:
                        try:
                            element = page.query_selector(selector)
                            if element and element.is_visible():
                                has_apply_button = True
                                break
                        except:
                            continue
                            
                except Exception as e:
                    logger.debug(f"Could not check for apply button: {e}")
                
                # If we have an apply button or no closure indicators, consider it active
                if has_apply_button or len(page_text) > 200:  # Has substantial content
                    logger.info(f"✅ Job {job_id} appears to be active")
                    return job_id, 'active', final_url, None
                else:
                    # Page loaded but seems empty or minimal
                    logger.info(f"⚠️ Job {job_id} has minimal content")
                    return job_id, 'inactive', final_url, "Page has minimal content"
                
            except PlaywrightTimeoutError as e:
                error_msg = f"Timeout loading page (attempt {attempt + 1})"
                logger.warning(f"Timeout for job {job_id}: {job_url}")
                if attempt == MAX_RETRIES - 1:
                    return job_id, 'error', None, error_msg
                time.sleep(2)
                
            except Exception as e:
                error_msg = f"Exception: {str(e)}"
                logger.error(f"Error checking job {job_id}: {e}")
                if attempt == MAX_RETRIES - 1:
                    return job_id, 'error', None, error_msg
                time.sleep(2)
        
        error_msg = f"Max retries ({MAX_RETRIES}) exceeded"
        return job_id, 'error', None, error_msg
    
    def verify_jobs(self, jobs: List[Dict], browser) -> List[Tuple[str, str, Optional[str], Optional[str]]]:
        """
        Verify a list of jobs
        
        Args:
            jobs: List of job documents from MongoDB
            browser: Playwright browser instance
            
        Returns:
            List of (job_id, status, final_url, reason) tuples
        """
        results = []
        
        for i, job in enumerate(jobs, 1):
            job_id = str(job['_id'])
            job_url = job.get('job_link', '')
            job_title = job.get('title', 'Unknown')
            company = job.get('company', 'Unknown')
            
            logger.info(f"[{i}/{len(jobs)}] Verifying: {job_title} at {company}")
            
            if job_url:
                page = None
                try:
                    # Create a new page for each job
                    page = browser.new_page()
                    
                    # Set a reasonable user agent
                    page.set_extra_http_headers({
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    })
                    
                    result = self.check_job_link(page, job_url, job_id)
                    results.append(result)
                    
                    # Store result with job info
                    job_id, status, final_url, reason = result
                    
                    self.results.append({
                        'job_id': job_id,
                        'job_title': job_title,
                        'company': company,
                        'original_url': job_url,
                        'final_url': final_url or job_url,
                        'status': status,
                        'reason': reason or '',
                        'verified_at': datetime.now().isoformat()
                    })
                    
                    # Update counters
                    self.verified_count += 1
                    if status == 'active':
                        self.active_count += 1
                    elif status == 'inactive':
                        self.inactive_count += 1
                    else:
                        self.error_count += 1
                    
                except Exception as e:
                    logger.error(f"Task failed with exception: {e}")
                    self.error_count += 1
                    results.append((job_id, 'error', None, str(e)))
                finally:
                    # Close the page
                    if page:
                        try:
                            page.close()
                        except:
                            pass
                
                # Small delay between checks to be respectful
                if i < len(jobs):
                    time.sleep(1)
        
        return results
    
    def update_job_status(self, results: List[Tuple[str, str, Optional[str], Optional[str]]]):
        """
        Update MongoDB with link verification results
        
        Args:
            results: List of (job_id, status, final_url, reason) tuples
        """
        if not results:
            return
        
        for job_id, status, final_url, reason in results:
            try:
                update_data = {
                    'link_status': status,
                    'link_verified_at': datetime.now(),
                    'link_final_url': final_url,
                    'link_status_reason': reason
                }
                
                result = self.collection.update_one(
                    {'_id': ObjectId(job_id)},
                    {'$set': update_data}
                )
                
                if result.modified_count > 0:
                    logger.debug(f"Updated job {job_id} with status: {status}")
                else:
                    logger.warning(f"No changes made to job {job_id}")
                    
            except Exception as e:
                logger.error(f"Error updating job {job_id}: {e}")
    
    def save_results_to_csv(self, filename: str = None) -> Optional[str]:
        """Save verification results to CSV file"""
        if not self.results:
            logger.warning("No results to save to CSV")
            return None
        
        # Create data directory if it doesn't exist
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"job_link_verification_{timestamp}.csv"
        
        filepath = data_dir / filename
        
        # Define CSV headers
        headers = ['job_id', 'job_title', 'company', 'original_url', 'final_url', 'status', 'reason', 'verified_at']
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            
            for result in self.results:
                writer.writerow(result)
        
        logger.info(f"📁 Results saved to {filepath}")
        return str(filepath)
    
    def generate_summary(self) -> Dict:
        """Generate summary statistics"""
        summary = {
            'total_verified': self.verified_count,
            'active': self.active_count,
            'inactive': self.inactive_count,
            'errors': self.error_count,
            'active_percentage': (self.active_count / self.verified_count * 100) if self.verified_count > 0 else 0,
            'inactive_percentage': (self.inactive_count / self.verified_count * 100) if self.verified_count > 0 else 0
        }
        return summary
    
    def run_verification(self, limit: Optional[int] = None, skip_verified: bool = True, 
                        include_active: bool = False):
        """
        Main verification process
        
        Args:
            limit: Maximum number of jobs to verify
            skip_verified: Skip jobs that were already verified
            include_active: Include jobs with 'active' status for re-verification
        """
        self.start_time = time.time()
        
        try:
            # Setup MongoDB connection
            self.setup_mongodb_connection()
            
            # Get jobs to verify
            jobs = self.get_jobs_to_verify(limit, skip_verified, include_active)
            
            if not jobs:
                logger.info("No jobs found to verify")
                return
            
            logger.info(f"Starting verification for {len(jobs)} jobs...")
            
            # Setup browser
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=HEADLESS)
                
                try:
                    # Verify all jobs
                    results = self.verify_jobs(jobs, browser)
                    
                    # Update MongoDB
                    self.update_job_status(results)
                    
                finally:
                    browser.close()
            
            # Save results to CSV
            csv_file = self.save_results_to_csv()
            
            # Generate and display summary
            summary = self.generate_summary()
            total_time = time.time() - self.start_time
            
            logger.info("=" * 60)
            logger.info("✅ Verification completed!")
            logger.info("=" * 60)
            logger.info(f"📊 Total verified: {summary['total_verified']}")
            logger.info(f"✅ Active jobs: {summary['active']} ({summary['active_percentage']:.1f}%)")
            logger.info(f"❌ Inactive jobs: {summary['inactive']} ({summary['inactive_percentage']:.1f}%)")
            logger.info(f"⚠️ Errors: {summary['errors']}")
            logger.info(f"⏱️ Total time: {total_time:.2f} seconds")
            logger.info(f"🚀 Average rate: {summary['total_verified'] / total_time:.2f} jobs/sec")
            if csv_file:
                logger.info(f"📁 Results saved to: {csv_file}")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            raise
        finally:
            if self.mongo_client:
                self.mongo_client.close()


def main():
    """Main function"""
    verifier = JobLinkVerifier()
    
    print("Job Link Verifier")
    print("=" * 60)
    print("This script will check if job postings are still active by:")
    print("  • Opening each job link")
    print("  • Detecting redirects")
    print("  • Looking for 'job closed' indicators")
    print("  • Updating MongoDB with verification status")
    print("=" * 60)
    
    try:
        # Setup MongoDB connection first to check counts
        verifier.setup_mongodb_connection()
        
        base_filter = {
            'job_link': {'$exists': True, '$ne': ''},
            'jd_extraction': True,
            'link_type': 'greenhouse',
            'cycle': 4
        }
        
        # Count jobs needing verification
        total_jobs = verifier.collection.count_documents(base_filter)
        
        # For unverified jobs, add link_status condition
        unverified_filter = dict(base_filter)
        unverified_filter['link_status'] = {'$exists': False}
        unverified_jobs = verifier.collection.count_documents(unverified_filter)
        
        # For active jobs, add link_status condition
        active_filter = dict(base_filter)
        active_filter['link_status'] = 'active'
        active_jobs = verifier.collection.count_documents(active_filter)
        
        logger.info(f"Base filter used for counts: {base_filter}")
        
        print(f"\n📊 Total jobs with links: {total_jobs}")
        print(f"📊 Unverified jobs: {unverified_jobs}")
        print(f"📊 Active jobs (previously verified): {active_jobs}")
        
        # Determine verification scope
        skip_verified = True
        include_active = False
        
        # Always show options if there are unverified or active jobs
        print("\nVerification options:")
        if unverified_jobs == 0:
            print("  1. Re-check active jobs only")
            print("  2. Re-verify all jobs (including inactive)")
            choice = input("Select option (1/2, default 1): ").strip()
            
            if choice == '2':
                skip_verified = False
                include_active = False
                print(f"\n🔄 Will re-verify all {total_jobs} jobs")
            else:
                skip_verified = True
                include_active = True
                print(f"\n🔄 Will re-check {active_jobs} active jobs")
        else:
            print("  1. Verify only unverified jobs")
            print("  2. Verify unverified jobs + re-check active jobs")
            print("  3. Re-verify all jobs (including inactive)")
            choice = input("Select option (1/2/3, default 1): ").strip()
            
            if choice == '2':
                skip_verified = True
                include_active = True
                print(f"\n🔄 Will verify {unverified_jobs} unverified + {active_jobs} active jobs = {unverified_jobs + active_jobs} total")
            elif choice == '3':
                skip_verified = False
                include_active = False
                print(f"\n🔄 Will re-verify all {total_jobs} jobs")
            else:
                skip_verified = True
                include_active = False
                print(f"\n🔄 Will verify {unverified_jobs} unverified jobs")
        
        limit_input = input("\nEnter number of jobs to verify (press Enter for all): ").strip()
        limit = int(limit_input) if limit_input else None
        
        headless_input = input(f"Run in headless mode? (y/n, default y): ").strip().lower()
        if headless_input == 'n':
            global HEADLESS
            HEADLESS = False
        
        print(f"\n🚀 Starting verification...")
        print(f"  • Limit: {limit if limit else 'All selected jobs'}")
        print(f"  • Headless mode: {HEADLESS}")
        print(f"  • Skip verified: {skip_verified}")
        print(f"  • Include active for re-check: {include_active}")
        print("-" * 60)
        
        verifier.run_verification(limit=limit, skip_verified=skip_verified, include_active=include_active)
        
    except KeyboardInterrupt:
        logger.info("\nVerification interrupted by user")
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        raise


if __name__ == "__main__":
    main()

