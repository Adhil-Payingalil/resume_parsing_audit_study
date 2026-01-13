import os
import time
import json
import csv
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import agentql
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, DuplicateKeyError
import logging


# Custom exceptions for AgentQL errors
class AgentQLLimitError(Exception):
    """Raised when AgentQL API limit is reached"""
    pass


class AgentQLCriticalError(Exception):
    """Raised when a critical AgentQL error occurs that should stop processing"""
    pass

# Load environment variables
load_dotenv()

# Set up AgentQL API key
os.environ["AGENTQL_API_KEY"] = os.getenv("AGENTQL_API_KEY")

# Create logs directory if it doesn't exist
logs_dir = Path('logs')
logs_dir.mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(logs_dir / 'job_description_dynamic_extractor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "Resume_study")
MONGODB_COLLECTION = "Job_postings_greenhouse"

# MongoDB job selection filter configuration
DEFAULT_JOB_FILTER = {
    "cycle": 3,
    "link_type": "greenhouse"
}

MONGODB_JOB_FILTER = DEFAULT_JOB_FILTER.copy()
env_job_filter = os.getenv("MONGODB_JOB_FILTER")
if env_job_filter:
    try:
        parsed_filter = json.loads(env_job_filter)
        if isinstance(parsed_filter, dict):
            MONGODB_JOB_FILTER = parsed_filter
            logger.info(f"Using MongoDB job filter from environment: {MONGODB_JOB_FILTER}")
        else:
            logger.warning("MONGODB_JOB_FILTER environment variable must be a JSON object. Using default filter.")
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse MONGODB_JOB_FILTER environment variable: {e}. Using default filter.")

# Browser settings
HEADLESS = False  # Set to True for headless mode
TIMEOUT = 30000  # 30 seconds timeout for page.goto()
WAIT_FOR_NETWORKIDLE = True  # Set to False to skip networkidle wait (useful for slow sites)
NETWORKIDLE_TIMEOUT = 15000  # 15 seconds timeout for networkidle (shorter than TIMEOUT)
MAX_RETRIES = 3
BATCH_SIZE = 5  # Process 5 jobs concurrently

# Retry configuration
RETRY_PREVIOUSLY_FAILED = True  # Set to True to retry jobs that have retry_attempted_at field
                                  # Set to False to only process jobs that have never been retried

class JobDescriptionDynamicExtractor:
    def __init__(self):
        self.mongo_client = None
        self.collection = None
        self.processed_count = 0
        self.failed_count = 0
        self.start_time = None
        self.results = []
        self.job_info = {}  # Store job details (URL, title) for CSV output
        self.should_stop = False  # Flag to stop processing on critical errors
        
    async def setup_mongodb_connection(self):
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

    def check_agentql_error(self, error_message: str) -> None:
        """
        Check if error is an AgentQL critical error and raise appropriate exception
        
        Args:
            error_message: The error message string to check
            
        Raises:
            AgentQLLimitError: If API limit is reached
            AgentQLCriticalError: If other critical AgentQL error occurs
        """
        error_lower = str(error_message).lower()
        
        # Check for API limit errors
        limit_indicators = [
            'apikeyerror',  # AgentQL APIKeyError
            'rate limit',
            'quota exceeded',
            'limit reached',
            'limit has been reached',
            'api limit',
            'api key limit',
            'too many requests',
            'usage limit',
            'monthly limit',
            'credit limit',
            '429',  # HTTP 429 Too Many Requests
        ]
        
        if any(indicator in error_lower for indicator in limit_indicators):
            logger.error(f"🚨 AgentQL API limit reached: {error_message}")
            raise AgentQLLimitError(f"AgentQL API limit reached: {error_message}")
        
        # Check for authentication/API key errors (excluding limit-related errors which are checked above)
        auth_indicators = [
            'unauthorized',
            'invalid api key',
            'authentication failed',
            '401',  # HTTP 401 Unauthorized
            '403',  # HTTP 403 Forbidden
        ]
        
        if any(indicator in error_lower for indicator in auth_indicators):
            logger.error(f"🚨 AgentQL authentication error: {error_message}")
            raise AgentQLCriticalError(f"AgentQL authentication error: {error_message}")
        
        # Check for service unavailable errors
        service_indicators = [
            'service unavailable',
            'server error',
            'internal server error',
            '500',  # HTTP 500 Internal Server Error
            '502',  # HTTP 502 Bad Gateway
            '503',  # HTTP 503 Service Unavailable
        ]
        
        if any(indicator in error_lower for indicator in service_indicators):
            # Log but don't raise - these might be temporary
            logger.warning(f"⚠️ AgentQL service error (may be temporary): {error_message}")


    def build_job_query(self, base_query: Dict) -> Dict:
        """
        Combine the base query with the configured MongoDB job filter.
        """
        if not MONGODB_JOB_FILTER:
            return base_query
        return {
            '$and': [
                MONGODB_JOB_FILTER.copy(),
                base_query
            ]
        }

    async def count_failed_jobs(self) -> int:
        """
        Count total number of jobs with jd_extraction = False
        Respects RETRY_PREVIOUSLY_FAILED configuration.
        
        Returns:
            Total count of failed jobs
        """
        query = {
            'job_link': {'$exists': True, '$ne': ''},
            'jd_extraction': False
        }
        
        # Apply retry filter based on configuration
        if not RETRY_PREVIOUSLY_FAILED:
            # Only get jobs that have NOT been retried before
            query['retry_attempted_at'] = {'$exists': False}
        # If RETRY_PREVIOUSLY_FAILED is True, we get all failed jobs (including previously retried ones)
        
        query = self.build_job_query(query)
        
        count = self.collection.count_documents(query)
        logger.info(f"Total jobs with jd_extraction = False: {count}")
        if not RETRY_PREVIOUSLY_FAILED:
            logger.info(f"(Excluding previously retried jobs based on RETRY_PREVIOUSLY_FAILED=False)")
        return count

    async def get_failed_jobs(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Get jobs from MongoDB that have jd_extraction = False
        Respects RETRY_PREVIOUSLY_FAILED configuration.
        
        Args:
            limit: Maximum number of jobs to process (None for all)
            
        Returns:
            List of job documents
        """
        query = {
            'job_link': {'$exists': True, '$ne': ''},
            'jd_extraction': False
        }
        
        # Apply retry filter based on configuration
        if not RETRY_PREVIOUSLY_FAILED:
            # Only get jobs that have NOT been retried before
            query['retry_attempted_at'] = {'$exists': False}
        # If RETRY_PREVIOUSLY_FAILED is True, we get all failed jobs (including previously retried ones)
        
        query = self.build_job_query(query)
        
        # Get total count first
        total_count = await self.count_failed_jobs()
        
        cursor = self.collection.find(query, {
            '_id': 1, 
            'job_link': 1, 
            'title': 1, 
            'company': 1, 
            'api_error': 1,
            'retry_attempted_at': 1,
            'created_at': 1
        }).sort('created_at', -1)  # Most recent first
        
        if limit:
            jobs = list(cursor.limit(limit))
            logger.info(f"Retrieved {len(jobs)} jobs (limited to {limit} out of {total_count} total)")
        else:
            jobs = list(cursor)
            logger.info(f"Retrieved {len(jobs)} jobs out of {total_count} total")
        
        return jobs

    def validate_job_description(self, description: str, job_id: str) -> Tuple[bool, Optional[str]]:
        """
        Validate extracted job description for quality and completeness
        
        Args:
            description: The extracted job description text
            job_id: Job ID for logging
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not description or len(description.strip()) == 0:
            return False, "Empty description"
        
        # Remove job title header if present to get actual content length
        content = description
        if content.startswith('# '):
            lines = content.split('\n', 2)
            if len(lines) >= 3:
                content = lines[2]  # Get content after title and empty line
        
        content_lower = content.lower()
        
        # 1. MINIMUM LENGTH CHECK - At least 200 characters of actual content
        MIN_LENGTH = 200
        if len(content.strip()) < MIN_LENGTH:
            logger.warning(f"Job {job_id}: Description too short ({len(content)} chars, minimum {MIN_LENGTH})")
            return False, f"Description too short: {len(content)} characters (minimum {MIN_LENGTH})"
        
        # 2. NON-JOB CONTENT DETECTION - Check for forms, surveys, error pages
        non_job_patterns = [
            'equal employment opportunity policy',
            'government reporting purposes',
            'self-identification survey',
            'veterans readjustment assistance act',
            'federal contractor or subcontractor',
            'omb control number 1250-0005',
            'form cc-305',
            'page 1 of 1',
            'completing this form is voluntary',
            'vietnam era veterans readjustment',
            'page not found',
            '404 error',
            'access denied',
            'permission denied',
            'session expired',
            'please log in',
            'cookies must be enabled',
            'javascript must be enabled'
        ]
        
        non_job_matches = [pattern for pattern in non_job_patterns if pattern in content_lower]
        if non_job_matches:
            logger.warning(f"Job {job_id}: Contains non-job content patterns: {non_job_matches[:3]}")
            return False, f"Non-job content detected: {', '.join(non_job_matches[:2])}"
        
        # 3. CONTENT QUALITY CHECK - Ensure it's not just a single paragraph or header
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        # Check if there are at least 5 non-empty lines OR substantial paragraphs
        substantial_lines = [line for line in lines if len(line) > 20]
        
        # Alternative: Check for substantial paragraphs (separated by blank lines)
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        substantial_paragraphs = [p for p in paragraphs if len(p) > 100]
        
        # Pass if either: 5+ substantial lines OR 3+ substantial paragraphs
        if len(substantial_lines) < 5 and len(substantial_paragraphs) < 3:
            logger.warning(f"Job {job_id}: Too few content segments ({len(substantial_lines)} lines, {len(substantial_paragraphs)} paragraphs)")
            return False, f"Incomplete extraction: only {len(substantial_lines)} substantial lines and {len(substantial_paragraphs)} paragraphs"
        
        # 4. KEYWORD VALIDATION - Check for typical job posting keywords
        # At least 2 of these categories should be present
        keyword_categories = {
            'responsibilities': ['responsibilities', 'duties', 'what you\'ll do', 'what you will do', 'you will'],
            'qualifications': ['qualifications', 'requirements', 'experience', 'skills', 'education'],
            'role_description': ['role', 'position', 'job', 'opportunity', 'candidate'],
            'action_verbs': ['manage', 'develop', 'lead', 'work', 'collaborate', 'support', 'ensure', 'create', 'maintain']
        }
        
        categories_found = 0
        for category, keywords in keyword_categories.items():
            if any(keyword in content_lower for keyword in keywords):
                categories_found += 1
        
        if categories_found < 2:
            logger.warning(f"Job {job_id}: Missing key job description elements (found {categories_found}/4 categories)")
            return False, f"Incomplete job description: missing key elements ({categories_found}/4 categories present)"
        
        # 5. STRUCTURE VALIDATION - Check for section headers or structured content
        # Look for common section indicators
        section_indicators = [
            'responsibilities', 'requirements', 'qualifications', 'about', 
            'what you', 'who you', 'we are looking', 'the ideal', 'benefits',
            'skills', 'experience', 'education', 'duties', 'overview'
        ]
        
        sections_found = sum(1 for indicator in section_indicators if indicator in content_lower)
        
        if sections_found < 2:
            logger.warning(f"Job {job_id}: Lacks structured sections (found {sections_found} sections)")
            return False, f"Unstructured content: only {sections_found} recognizable sections"
        
        # All validations passed
        logger.info(f"Job {job_id}: Description passed all validation checks ({len(content)} chars, {len(substantial_lines)} lines, {len(substantial_paragraphs)} paragraphs, {categories_found} categories, {sections_found} sections)")
        return True, None

    def extract_job_description_with_agentql_sync(self, page, job_url: str, job_id: str, job_title: str = None) -> Tuple[str, bool, Optional[str]]:
        """
        Extract job description from a single URL using AgentQL (sync version)
        
        Args:
            page: Playwright page wrapped with AgentQL
            job_url: The job posting URL
            job_id: MongoDB document ID for logging
            job_title: Job title to prepend to descriptions
            
        Returns:
            Tuple of (job_id, success, description, error_message)
        """
        if not job_url or not job_url.startswith('http'):
            error_msg = f"Invalid URL: {job_url}"
            logger.warning(f"Invalid URL for job {job_id}: {job_url}")
            return job_id, False, None, error_msg
            
        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"Processing job {job_id} (attempt {attempt + 1}/{MAX_RETRIES}): {job_url}")
                
                # Navigate to the job URL
                page.goto(job_url, timeout=TIMEOUT, wait_until='domcontentloaded')
                
                # Wait for page to load completely - but don't fail if networkidle times out
                try:
                    page.wait_for_load_state('load', timeout=10000)
                    logger.debug(f"Job {job_id}: Page 'load' event completed")
                except Exception as e:
                    logger.warning(f"Job {job_id}: Load state wait timed out, continuing anyway: {e}")
                
                # Try to wait for networkidle, but don't fail if it times out
                # Some sites have continuous background requests that prevent networkidle
                if WAIT_FOR_NETWORKIDLE:
                    try:
                        page.wait_for_load_state('networkidle', timeout=NETWORKIDLE_TIMEOUT)
                        logger.debug(f"Job {job_id}: Page reached 'networkidle' state")
                    except Exception as e:
                        logger.warning(f"Job {job_id}: Network idle not achieved (common for sites with analytics), continuing anyway")
                else:
                    logger.debug(f"Job {job_id}: Skipping networkidle wait (WAIT_FOR_NETWORKIDLE=False)")
                
                # Wait for any popups and dismiss them
                self.handle_popups_sync(page)
                
                # Wait for dynamic content to load
                time.sleep(3)
                
                # Try to wait for common job description selectors
                try:
                    page.wait_for_selector('body', timeout=10000)
                    # Wait for potential job description elements
                    selectors_to_wait = [
                        '[class*="job-description"]',
                        '[class*="description"]',
                        '[class*="content"]',
                        'main',
                        'article',
                        '.content',
                        '#content'
                    ]
                    
                    for selector in selectors_to_wait:
                        try:
                            page.wait_for_selector(selector, timeout=2000)
                            break
                        except:
                            continue
                            
                except Exception as e:
                    logger.warning(f"Could not wait for specific selectors for job {job_id}: {e}")
                
                # Scroll the page to trigger lazy-loaded content
                try:
                    logger.info(f"Scrolling page to load dynamic content for job {job_id}")
                    # Scroll down in increments to trigger lazy loading
                    for i in range(3):
                        page.evaluate('window.scrollBy(0, window.innerHeight)')
                        time.sleep(0.5)
                    # Scroll back to top
                    page.evaluate('window.scrollTo(0, 0)')
                    time.sleep(1)
                except Exception as e:
                    logger.warning(f"Could not scroll page for job {job_id}: {e}")
                
                # Use AgentQL to extract job description with multiple strategies
                try:
                    # Verify AgentQL is working
                    if not hasattr(page, 'query_data'):
                        raise Exception("AgentQL not properly initialized - page object missing 'query_data' method")
                    
                    description = None
                    
                    # STRATEGY 1: Comprehensive multi-field query
                    logger.info(f"Strategy 1: Attempting comprehensive extraction for job {job_id}")
                    comprehensive_query = """
                    {
                        job_description
                        job_overview
                        responsibilities
                        requirements
                        qualifications
                        about_role
                        main_content
                    }
                    """
                    
                    try:
                        result = page.query_data(comprehensive_query)
                        if result:
                            # Combine all found fields
                            parts = []
                            for key in ['job_description', 'job_overview', 'about_role', 'responsibilities', 
                                       'requirements', 'qualifications', 'main_content']:
                                if key in result and result[key]:
                                    content = result[key].strip()
                                    if content and len(content) > 50:  # Only include substantial content
                                        parts.append(content)
                            
                            if parts:
                                # Remove duplicates by checking if content is already included
                                unique_parts = []
                                for part in parts:
                                    # Check if this part is not a substring of any existing part
                                    is_duplicate = any(part in existing or existing in part 
                                                      for existing in unique_parts)
                                    if not is_duplicate:
                                        unique_parts.append(part)
                                
                                description = '\n\n'.join(unique_parts)
                                logger.info(f"Strategy 1 successful: Combined {len(unique_parts)} sections for job {job_id}")
                    except Exception as e:
                        logger.warning(f"Strategy 1 failed for job {job_id}: {e}")
                        # Check if this is a critical AgentQL error (API limit reached)
                        self.check_agentql_error(str(e))
                    
                    # STRATEGY 2: Simple job_description query (fallback)
                    if not description or len(description.strip()) < 200:
                        logger.info(f"Strategy 2: Attempting simple extraction for job {job_id}")
                        simple_query = """
                        {
                            job_description
                        }
                        """
                        try:
                            result = page.query_data(simple_query)
                            if result and 'job_description' in result and result['job_description']:
                                fallback_desc = result['job_description'].strip()
                                if len(fallback_desc) > len(description or ''):
                                    description = fallback_desc
                                    logger.info(f"Strategy 2 provided better content for job {job_id}")
                        except Exception as e:
                            logger.warning(f"Strategy 2 failed for job {job_id}: {e}")
                            # Check if this is a critical AgentQL error (API limit reached)
                            self.check_agentql_error(str(e))
                    
                    # STRATEGY 3: Extract main article/content area
                    if not description or len(description.strip()) < 200:
                        logger.info(f"Strategy 3: Attempting main content extraction for job {job_id}")
                        content_query = """
                        {
                            main_content
                            article_content
                            page_content
                        }
                        """
                        try:
                            result = page.query_data(content_query)
                            if result:
                                for key in ['main_content', 'article_content', 'page_content']:
                                    if key in result and result[key]:
                                        content = result[key].strip()
                                        if len(content) > len(description or ''):
                                            description = content
                                            logger.info(f"Strategy 3 successful with {key} for job {job_id}")
                                            break
                        except Exception as e:
                            logger.warning(f"Strategy 3 failed for job {job_id}: {e}")
                            # Check if this is a critical AgentQL error (API limit reached)
                            self.check_agentql_error(str(e))
                    
                    # STRATEGY 4: Direct CSS selector extraction (last resort)
                    if not description or len(description.strip()) < 200:
                        logger.info(f"Strategy 4: Attempting direct CSS selector extraction for job {job_id}")
                        css_selectors = [
                            'main',
                            'article',
                            '[class*="job-description"]',
                            '[class*="description"]',
                            '[id*="job-description"]',
                            '[id*="description"]',
                            '.content',
                            '#content',
                            '[role="main"]',
                            'body'
                        ]
                        
                        for selector in css_selectors:
                            try:
                                element = page.query_selector(selector)
                                if element:
                                    text = element.inner_text()
                                    if text and len(text.strip()) > len(description or ''):
                                        description = text.strip()
                                        logger.info(f"Strategy 4 successful with selector '{selector}' for job {job_id}")
                                        break
                            except Exception as e:
                                continue
                    
                    # Process the extracted description
                    if description and description.strip():
                        # Add job title to the description if provided
                        if job_title:
                            description = f"# {job_title}\n\n{description.strip()}"
                        
                        # VALIDATE the extracted description before marking as successful
                        is_valid, validation_error = self.validate_job_description(description, job_id)
                        
                        if is_valid:
                            logger.info(f"✅ Successfully extracted and validated job description for job {job_id}")
                            return job_id, True, description, None
                        else:
                            # Description extracted but failed validation
                            logger.warning(f"⚠️ Job description extracted but failed validation for job {job_id}: {validation_error}")
                            return job_id, False, description, f"Validation failed: {validation_error}"
                    else:
                        logger.warning(f"⚠️ All extraction strategies failed for job {job_id}")
                        return job_id, False, None, "All extraction strategies failed"
                        
                except Exception as e:
                    logger.error(f"AgentQL query failed for job {job_id}: {e}")
                    # Check if this is a critical AgentQL error
                    try:
                        self.check_agentql_error(str(e))
                    except (AgentQLLimitError, AgentQLCriticalError) as agentql_error:
                        # Re-raise to be caught by outer handler
                        raise agentql_error
                    
                    if attempt == MAX_RETRIES - 1:
                        return job_id, False, None, f"AgentQL query failed: {str(e)}"
                    time.sleep(2)
                    
            except (AgentQLLimitError, AgentQLCriticalError) as e:
                # Critical AgentQL error - propagate to stop processing
                logger.critical(f"🚨 Critical AgentQL error encountered: {e}")
                raise
            except Exception as e:
                error_msg = f"Exception on attempt {attempt + 1}: {str(e)}"
                logger.error(f"Error processing job {job_id}: {e}")
                # Check if this is a critical AgentQL error
                try:
                    self.check_agentql_error(str(e))
                except (AgentQLLimitError, AgentQLCriticalError) as agentql_error:
                    # Re-raise to be caught by outer handler
                    raise agentql_error
                
                if attempt == MAX_RETRIES - 1:
                    return job_id, False, None, error_msg
                time.sleep(2)
        
        error_msg = f"Max retries ({MAX_RETRIES}) exceeded for URL: {job_url}"
        return job_id, False, None, error_msg

    def handle_popups_sync(self, page):
        """Handle common popups that might appear on job pages (sync version)"""
        try:
            # Common popup selectors
            popup_selectors = [
                '[class*="popup"]',
                '[class*="modal"]',
                '[class*="overlay"]',
                '[class*="cookie"]',
                '[class*="consent"]',
                '[class*="banner"]',
                '[id*="popup"]',
                '[id*="modal"]',
                '[id*="cookie"]',
                '[id*="consent"]',
                '[id*="banner"]',
                'button[class*="close"]',
                'button[class*="dismiss"]',
                'button[class*="accept"]',
                'button[class*="decline"]',
                '[aria-label*="close"]',
                '[aria-label*="dismiss"]',
                '[aria-label*="accept"]',
                '[aria-label*="decline"]'
            ]
            
            # Wait a bit for popups to appear
            time.sleep(1)
            
            for selector in popup_selectors:
                try:
                    # Check if popup exists and is visible
                    popup = page.query_selector(selector)
                    if popup and popup.is_visible():
                        logger.info(f"Found popup with selector: {selector}")
                        
                        # Try to find close button within the popup
                        close_buttons = [
                            'button[class*="close"]',
                            'button[class*="dismiss"]',
                            'button[class*="accept"]',
                            'button[class*="decline"]',
                            '[aria-label*="close"]',
                            '[aria-label*="dismiss"]',
                            '[aria-label*="accept"]',
                            '[aria-label*="decline"]',
                            'button',
                            'a'
                        ]
                        
                        for close_selector in close_buttons:
                            try:
                                close_btn = popup.query_selector(close_selector)
                                if close_btn and close_btn.is_visible():
                                    close_btn.click()
                                    logger.info(f"Clicked close button: {close_selector}")
                                    time.sleep(1)
                                    break
                            except:
                                continue
                        
                        # If no close button found, try clicking outside or pressing Escape
                        try:
                            page.keyboard.press('Escape')
                            logger.info("Pressed Escape to close popup")
                            time.sleep(1)
                        except:
                            pass
                            
                except Exception as e:
                    # Popup not found or error handling it, continue
                    continue
                    
        except Exception as e:
            logger.warning(f"Error handling popups: {e}")

    def process_batch_sync(self, jobs: List[Dict], browser) -> List[Tuple[str, bool, Optional[str], Optional[str]]]:
        """
        Process a batch of jobs sequentially using sync Playwright
        
        Args:
            jobs: List of job documents from MongoDB
            browser: Playwright browser instance
            
        Returns:
            List of (job_id, success, description, error_message) tuples
            
        Raises:
            AgentQLLimitError: If API limit is reached
            AgentQLCriticalError: If critical AgentQL error occurs
        """
        results = []
        
        for job in jobs:
            # Check if we should stop processing
            if self.should_stop:
                logger.warning("⚠️ Stopping batch processing due to previous critical error")
                break
            
            job_id = str(job['_id'])
            job_url = job.get('job_link', '')
            job_title = job.get('title', '')
            
            # Store job information for CSV output
            self.job_info[job_id] = {
                'job_url': job_url,
                'job_title': job_title
            }
            
            if job_url:
                page = None
                try:
                    # Create a new page for each job
                    page = browser.new_page()
                    wrapped_page = agentql.wrap(page)
                    
                    result = self.extract_job_description_with_agentql_sync(wrapped_page, job_url, job_id, job_title)
                    results.append(result)
                    
                except (AgentQLLimitError, AgentQLCriticalError) as e:
                    # Critical AgentQL error - stop processing
                    logger.critical(f"🚨 Critical AgentQL error in batch processing: {e}")
                    self.should_stop = True
                    self.failed_count += 1
                    results.append((job_id, False, None, f"Critical AgentQL error: {str(e)}"))
                    # Re-raise to stop the entire processing
                    raise
                except Exception as e:
                    logger.error(f"Task failed with exception: {e}")
                    self.failed_count += 1
                    results.append((job_id, False, None, str(e)))
                finally:
                    # Close the page
                    if page:
                        try:
                            page.close()
                        except:
                            pass
        
        return results

    def update_job_descriptions_sync(self, results: List[Tuple[str, bool, Optional[str], Optional[str]]]):
        """
        Update MongoDB with job descriptions (sync version)
        
        Args:
            results: List of (job_id, success, description, error_message) tuples
        """
        if not results:
            return
            
        from bson import ObjectId
        
        # Update jobs individually
        for job_id, success, description, error_message in results:
            try:
                if success and description:
                    # Successfully extracted AND validated description
                    update_data = {
                        'job_description': description,
                        'jd_extraction': True,
                        'api_error': None,  # Clear any previous error
                        'retry_error': None,  # Clear any previous retry error
                        'retry_extracted_at': datetime.now()
                    }
                    
                    result = self.collection.update_one(
                        {'_id': ObjectId(job_id)},
                        {'$set': update_data}
                    )
                    
                    if result.modified_count > 0:
                        self.processed_count += 1
                        logger.info(f"✅ Updated job {job_id} with validated description")
                        # Get job information for CSV
                        job_info = self.job_info.get(job_id, {})
                        
                        self.results.append({
                            'job_id': job_id,
                            'job_title': job_info.get('job_title', ''),
                            'job_link': job_info.get('job_url', ''),
                            'status': 'success',
                            'description_length': len(description),
                            'job_description': description,
                            'error': None
                        })
                    else:
                        logger.warning(f"⚠️ No changes made to job {job_id}")
                        
                elif not success and description:
                    # Description extracted but failed validation - store for debugging
                    update_data = {
                        'job_description': description,  # Store the partial extraction
                        'jd_extraction': False,  # Mark as failed
                        'retry_error': error_message,
                        'retry_attempted_at': datetime.now()
                    }
                    
                    result = self.collection.update_one(
                        {'_id': ObjectId(job_id)},
                        {'$set': update_data}
                    )
                    
                    if result.modified_count > 0:
                        self.failed_count += 1
                        logger.info(f"⚠️ Job {job_id}: Extracted content failed validation, stored for review (Error: {error_message})")
                        # Get job information for CSV
                        job_info = self.job_info.get(job_id, {})
                        
                        self.results.append({
                            'job_id': job_id,
                            'job_title': job_info.get('job_title', ''),
                            'job_link': job_info.get('job_url', ''),
                            'status': 'validation_failed',
                            'description_length': len(description),
                            'job_description': description,
                            'error': error_message
                        })
                    else:
                        logger.warning(f"⚠️ No changes made to job {job_id}")
                        
                else:
                    # Failed to extract description at all
                    update_data = {
                        'jd_extraction': False,
                        'retry_error': error_message,
                        'retry_attempted_at': datetime.now()
                    }
                    
                    result = self.collection.update_one(
                        {'_id': ObjectId(job_id)},
                        {'$set': update_data}
                    )
                    
                    if result.modified_count > 0:
                        self.failed_count += 1
                        logger.info(f"❌ Marked job {job_id} as failed (Error: {error_message})")
                        # Get job information for CSV
                        job_info = self.job_info.get(job_id, {})
                        
                        self.results.append({
                            'job_id': job_id,
                            'job_title': job_info.get('job_title', ''),
                            'job_link': job_info.get('job_url', ''),
                            'status': 'failed',
                            'description_length': 0,
                            'job_description': '',
                            'error': error_message
                        })
                    else:
                        logger.warning(f"⚠️ No changes made to job {job_id}")
                        
            except Exception as e:
                logger.error(f"Error updating job {job_id}: {e}")
                self.failed_count += 1


    def save_results_to_csv_sync(self, filename: str = None):
        """Save extraction results to CSV file (sync version)"""
        if not self.results:
            logger.warning("No results to save to CSV")
            return None
            
        # Create data directory if it doesn't exist
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"job_description_dynamic_results_{timestamp}.csv"
        
        filepath = data_dir / filename
        
        # Define CSV headers
        headers = ['job_id', 'job_title', 'job_link', 'status', 'description_length', 'job_description', 'error']
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            
            for result in self.results:
                writer.writerow(result)
        
        logger.info(f"Results saved to {filepath}")
        return str(filepath)


    def run_retry_extraction(self, limit: Optional[int] = None, batch_size: int = BATCH_SIZE):
        """
        Main retry extraction process (sync version)
        
        Args:
            limit: Maximum number of jobs to process
            batch_size: Number of jobs to process per batch
        """
        self.start_time = time.time()
        
        try:
            # Setup connections
            asyncio.run(self.setup_mongodb_connection())
            
            # Get failed jobs
            all_jobs = asyncio.run(self.get_failed_jobs(limit))
            
            if not all_jobs:
                logger.info("No jobs found with jd_extraction = False")
                return
            
            logger.info(f"Starting retry extraction for {len(all_jobs)} jobs...")
            
            # Setup browser with sync Playwright
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=HEADLESS)
                
                try:
                    # Process jobs in batches
                    for i in range(0, len(all_jobs), batch_size):
                        # Check if we should stop processing
                        if self.should_stop:
                            logger.warning("⚠️ Stopping extraction due to critical error")
                            break
                        
                        batch = all_jobs[i:i + batch_size]
                        batch_num = (i // batch_size) + 1
                        total_batches = (len(all_jobs) + batch_size - 1) // batch_size
                        
                        logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} jobs)")
                        
                        try:
                            # Process batch
                            results = self.process_batch_sync(batch, browser)
                            
                            # Update MongoDB
                            self.update_job_descriptions_sync(results)
                            
                            # Progress update
                            elapsed = time.time() - self.start_time
                            rate = (self.processed_count + self.failed_count) / elapsed if elapsed > 0 else 0
                            logger.info(f"Progress: {self.processed_count} processed, {self.failed_count} failed, {rate:.2f} jobs/sec")
                            
                        except (AgentQLLimitError, AgentQLCriticalError) as e:
                            logger.critical(f"🚨 Critical AgentQL error occurred: {e}")
                            logger.critical(f"⚠️ Stopping extraction after processing {self.processed_count + self.failed_count} jobs")
                            self.should_stop = True
                            break
                        
                        # Small delay between batches
                        if i + batch_size < len(all_jobs) and not self.should_stop:
                            time.sleep(2)
                finally:
                    browser.close()
                
                # Save results to CSV
                csv_file = self.save_results_to_csv_sync()
                
                # Final summary
                total_time = time.time() - self.start_time
                total_jobs = self.processed_count + self.failed_count
                
                print("\n" + "=" * 70)
                print("Extraction Summary".center(70))
                print("=" * 70)
                
                if self.should_stop:
                    logger.warning(f"⚠️ Extraction stopped early due to critical error!")
                    logger.warning(f"⚠️ Partial results have been saved")
                else:
                    logger.info(f"✅ Retry extraction completed!")
                
                logger.info(f"📊 Total processed successfully: {self.processed_count}")
                logger.info(f"❌ Total failed: {self.failed_count}")
                logger.info(f"📝 Total jobs attempted: {total_jobs}")
                logger.info(f"⏱️  Total time: {total_time:.2f} seconds")
                if total_jobs > 0:
                    logger.info(f"🚀 Average rate: {total_jobs / total_time:.2f} jobs/sec")
                    logger.info(f"✅ Success rate: {(self.processed_count / total_jobs * 100):.1f}%")
                if csv_file:
                    logger.info(f"📁 Results saved to: {csv_file}")
                print("=" * 70 + "\n")
                
        except AgentQLLimitError as e:
            logger.critical(f"🚨 AgentQL API limit reached: {e}")
            print(f"\n{'=' * 70}")
            print(f"🚨 CRITICAL ERROR: AgentQL API Limit Reached")
            print(f"{'=' * 70}")
            print(f"Error: {e}")
            print(f"\nThe script has stopped because the AgentQL API limit has been reached.")
            print(f"Please check your AgentQL usage limits and try again later.")
            print(f"\nPartial results (if any) have been saved to CSV.")
            print(f"{'=' * 70}\n")
            raise
        except AgentQLCriticalError as e:
            logger.critical(f"🚨 Critical AgentQL error: {e}")
            print(f"\n{'=' * 70}")
            print(f"🚨 CRITICAL ERROR: AgentQL Error")
            print(f"{'=' * 70}")
            print(f"Error: {e}")
            print(f"\nThe script has stopped due to a critical AgentQL error.")
            print(f"This could be due to authentication issues or service problems.")
            print(f"\nPartial results (if any) have been saved to CSV.")
            print(f"{'=' * 70}\n")
            raise
        except Exception as e:
            logger.error(f"Retry extraction failed: {e}")
            raise
        finally:
            if self.mongo_client:
                self.mongo_client.close()

def main():
    """Main function"""
    if not os.getenv("AGENTQL_API_KEY"):
        logger.error("❌ AGENTQL_API_KEY not found in environment variables")
        return
    
    extractor = JobDescriptionDynamicExtractor()
    
    # Display configuration
    print("\n" + "=" * 70)
    print("Job Description Dynamic Extractor".center(70))
    print("=" * 70)
    print(f"\n📋 Configuration:")
    print(f"  • Headless mode: {HEADLESS}")
    print(f"  • Page load timeout: {TIMEOUT/1000:.0f} seconds")
    print(f"  • Network idle timeout: {NETWORKIDLE_TIMEOUT/1000:.0f} seconds")
    print(f"  • Wait for network idle: {WAIT_FOR_NETWORKIDLE}")
    print(f"  • Max retries per job: {MAX_RETRIES}")
    print(f"  • Default batch size: {BATCH_SIZE}")
    print(f"  • Retry previously failed: {RETRY_PREVIOUSLY_FAILED}")
    if not RETRY_PREVIOUSLY_FAILED:
        print(f"    (Will only process jobs that have never been retried)")
    else:
        print(f"    (Will process all failed jobs, including previously retried ones)")
    print()
    
    try:
        # Setup MongoDB connection first
        asyncio.run(extractor.setup_mongodb_connection())
        
        # Check total count of failed jobs
        total_failed = asyncio.run(extractor.count_failed_jobs())
        if total_failed > 0:
            print(f"⚠️  Found {total_failed} jobs with jd_extraction = False")
            
            # Show preview of first 10 jobs
            failed_jobs = asyncio.run(extractor.get_failed_jobs(limit=10))
            if failed_jobs:
                print(f"\n📝 Preview of first {len(failed_jobs)} jobs:")
                for i, job in enumerate(failed_jobs[:5], 1):  # Show first 5
                    print(f"  {i}. {job.get('title', 'Unknown')} at {job.get('company', 'Unknown')}")
                    if job.get('retry_attempted_at'):
                        print(f"     ⚠️ Previously retried at: {job.get('retry_attempted_at')}")
                if len(failed_jobs) > 5:
                    print(f"  ... and {len(failed_jobs) - 5} more")
                print()
        else:
            print("\n✅ No failed jobs found to retry.")
            print("   All jobs have been successfully processed or no jobs match the retry criteria.")
            return
        
        # Get user input
        limit_input = input("Enter number of jobs to process (press Enter for all): ").strip()
        limit = int(limit_input) if limit_input else None
        
        batch_input = input(f"Enter batch size (default {BATCH_SIZE}): ").strip()
        batch_size = int(batch_input) if batch_input else BATCH_SIZE
        
        # Confirm processing
        print(f"\n{'=' * 70}")
        print(f"🚀 Starting retry extraction...")
        print(f"{'=' * 70}")
        print(f"  • Jobs to process: {limit if limit else f'All ({total_failed})'}")
        print(f"  • Batch size: {batch_size}")
        print(f"  • Headless mode: {HEADLESS}")
        print(f"  • Retry config: RETRY_PREVIOUSLY_FAILED = {RETRY_PREVIOUSLY_FAILED}")
        print(f"{'=' * 70}\n")
        
        extractor.run_retry_extraction(limit=limit, batch_size=batch_size)
        
    except KeyboardInterrupt:
        logger.info("\n⚠️  Retry extraction interrupted by user")
        print("\n⚠️  Process interrupted by user. Partial results may have been saved.")
    except AgentQLLimitError as e:
        # Already handled in run_retry_extraction, just exit gracefully
        pass
    except AgentQLCriticalError as e:
        # Already handled in run_retry_extraction, just exit gracefully
        pass
    except Exception as e:
        logger.error(f"❌ Retry extraction failed: {e}")
        print(f"\n❌ Fatal error: {e}")

if __name__ == "__main__":
    main()
