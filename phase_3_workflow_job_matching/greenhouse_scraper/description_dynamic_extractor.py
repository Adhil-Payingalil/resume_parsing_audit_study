import os
import time
import json
import csv
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import agentql
from playwright.async_api import async_playwright
import aiohttp
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

# Custom exception for Jina AI API errors
class JinaAICriticalError(Exception):
    """Custom exception for critical Jina AI API errors (e.g., invalid key, persistent rate limits)."""
    pass


# Load environment variables
load_dotenv()

# Set up AgentQL API key
os.environ["AGENTQL_API_KEY"] = os.getenv("AGENTQL_API_KEY")

# Jina AI API Configuration
JINAAI_API_KEY = os.getenv("JINAAI_API_KEY")
JINA_BASE_URL = "https://r.jina.ai/"
RATE_LIMIT_DELAY = 0.2  # 200ms between requests (5 requests per second)
JINA_TIMEOUT = 60 # 60 seconds timeout per request

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
    "cycle": 9,
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
JINA_BATCH_SIZE = 10 # Process 10 jobs concurrently for Jina AI

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
        self.http_session = None # Added http_session for Jina AI
        
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

    async def setup_http_session(self):
        """Set up aiohttp session with optimized settings for Jina AI"""
        connector = aiohttp.TCPConnector(
            limit=100,  # Total connection pool size
            limit_per_host=30,  # Per-host connection limit
            ttl_dns_cache=300,  # DNS cache TTL
            use_dns_cache=True,
        )
        
        # Timeout configuration aligned with Jina AI's processing time
        timeout = aiohttp.ClientTimeout(
            total=JINA_TIMEOUT,      # 60 seconds total
            connect=10,         # 10 seconds to establish connection
            sock_read=JINA_TIMEOUT   # 60 seconds to read response (matches Jina's x-timeout)
        )
        
        self.http_session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                'Authorization': f'Bearer {JINAAI_API_KEY}',
                'User-Agent': 'Job-Description-Dynamic-Extractor/1.0',
                'X-Wait-For-Selector': 'body, main, .content, .job-description, [role="main"]',
                'X-Wait-For-Timeout': '5000',  # Wait 5 seconds for selector
                'x-timeout': str(JINA_TIMEOUT)  # Overall timeout
            }
        )

    async def check_agentql_error(self, error_message: str) -> None:
        """
        Check if error is an AgentQL critical error and raise appropriate exception
        
        Args:
            error_message: The error message string to check
            
        Raises:
            AgentQLLimitError: If API limit is reached
            AgentQLCriticalError: If other critical AgentQL error occurs
            JinaAICriticalError: If a critical Jina AI error occurs
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

    async def check_jina_ai_error(self, error_message: str) -> None:
        """
        Check if error is a Jina AI critical error and raise appropriate exception
        
        Args:
            error_message: The error message string to check
            
        Raises:
            JinaAICriticalError: If a critical Jina AI error occurs
        """
        error_lower = str(error_message).lower()
        
        # Check for API key issues
        auth_indicators = [
            'unauthorized',
            'invalid api key',
            'authentication failed',
            '401',  # HTTP 401 Unauthorized
            '403',  # HTTP 403 Forbidden
        ]
        if any(indicator in error_lower for indicator in auth_indicators):
            logger.critical(f"❌ Jina AI API Unauthorized (401) or Forbidden (403): {error_message}. Check API key. Stopping extraction.")
            raise JinaAICriticalError(f"Jina AI API Unauthorized or Forbidden. Check JINAAI_API_KEY. Error: {error_message}")


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

    async def is_valid_description(self, description: str, job_id: str) -> Tuple[bool, Optional[str]]:
        """
        Validate extracted job description for quality based on word count.
        
        Args:
            description: The extracted job description text
            job_id: Job ID for logging
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not description or len(description.strip()) == 0:
            return False, "Empty description"
        
        word_count = len(description.split())
        MIN_WORDS = 50  # Minimum 50 words for a valid description
        
        if word_count < MIN_WORDS:
            logger.warning(f"Job {job_id}: Description too short ({word_count} words, minimum {MIN_WORDS})")
            return False, f"Description too short: {word_count} words (minimum {MIN_WORDS})"
        
        logger.info(f"Job {job_id}: Description passed word count validation ({word_count} words)")
        return True, None

    async def fetch_job_description_jina_ai(self, job_url: str, job_id: str, job_title: str = None) -> Tuple[str, Optional[str], bool, Optional[str]]:
        """
        Fetch job description from a single URL using Jina AI Reader API.
        
        Args:
            job_url: The job posting URL
            job_id: MongoDB document ID for logging
            job_title: Job title to prepend to clean extractions
            
        Returns:
            Tuple of (job_id, description, api_success, error_message) where:
            - api_success: True if API call succeeded, False if API returned error
            - error_message: Error details if API failed, None if succeeded
        """
        if not JINAAI_API_KEY:
            error_msg = "JINAAI_API_KEY not found in environment variables. Cannot use Jina AI."
            logger.error(f"❌ {error_msg}")
            return job_id, None, False, error_msg

        if not job_url or not job_url.startswith('http'):
            error_msg = f"Invalid URL: {job_url}"
            logger.warning(f"Invalid URL for job {job_id}: {job_url}")
            return job_id, None, False, error_msg
            
        # Construct Jina AI Reader URL
        jina_url = f"{JINA_BASE_URL}{job_url}"
        
        for attempt in range(MAX_RETRIES):
            try:
                async with self.http_session.get(jina_url) as response:
                    if response.status == 200:
                        content = await response.text()
                        
                        # Parse the response to extract job description
                        description, jd_extraction_success = self.extract_description_from_jina_content(content)
                        
                        if description:
                            if jd_extraction_success:
                                # Add job title to clean extractions
                                if job_title:
                                    description = f"# {job_title}\n\n{description}"
                                logger.info(f"✅ Successfully extracted clean job description for job {job_id} using Jina AI")
                            else:
                                logger.info(f"✅ Using full Jina AI content for job {job_id} (clean extraction failed)")
                            return job_id, (description, jd_extraction_success), True, None
                        else:
                            logger.warning(f"⚠️ No description found for job {job_id} using Jina AI")
                            return job_id, None, True, None
                    elif response.status == 429:
                        # Rate limited - wait longer
                        if attempt == MAX_RETRIES - 1: # Last attempt failed due to rate limit
                            logger.critical(f"❌ Persistent rate limiting (429) for job {job_id}. Max retries exceeded. Stopping extraction.")
                            raise JinaAICriticalError(f"Persistent rate limiting (429) after {MAX_RETRIES} attempts for URL: {job_url}")
                        
                        wait_time = (2 ** attempt) * 2  # Exponential backoff
                        logger.warning(f"Rate limited for job {job_id}, waiting {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    elif response.status in [401, 403]:
                        # Unauthorized or Forbidden - API key issue
                        error_msg = await response.text()
                        await self.check_jina_ai_error(f"{response.status} {error_msg}")

                    else:
                        error_msg = f"HTTP {response.status} error for URL: {job_url}"
                        logger.error(f"HTTP {response.status} for job {job_id}: {job_url}")
                        if attempt == MAX_RETRIES - 1:
                            return job_id, None, False, error_msg
                        await asyncio.sleep(1) # Small delay before retrying for other HTTP errors
                        
            except asyncio.TimeoutError:
                error_msg = f"Timeout after {MAX_RETRIES} attempts for URL: {job_url}"
                logger.error(f"Timeout for job {job_id} (attempt {attempt + 1})")
                if attempt == MAX_RETRIES - 1:
                    return job_id, None, False, error_msg
                await asyncio.sleep(2 ** attempt)
                
            except Exception as e:
                error_msg = f"Exception after {MAX_RETRIES} attempts: {str(e)} for URL: {job_url}"
                logger.error(f"Error fetching job {job_id}: {e}")
                if attempt == MAX_RETRIES - 1:
                    return job_id, None, False, error_msg
                await asyncio.sleep(1)
        
        error_msg = f"Max retries ({MAX_RETRIES}) exceeded for URL: {job_url}"
        return job_id, None, False, error_msg

    def extract_description_from_jina_content(self, content: str) -> tuple[Optional[str], bool]:
        """
        Extract job description from Jina AI response content with fallback
        
        Args:
            content: Raw content from Jina AI API
            
        Returns:
            Tuple of (extracted_description, jd_extraction_success)
            - If extraction works: (clean_description, True)
            - If extraction fails: (full_content, False)
        """
        try:
            if not content or len(content.strip()) == 0:
                return None, False

            # Check for common non-job content patterns (more specific patterns)
            content_lower = content.lower()
            non_job_patterns = [
                'equal employment opportunity policy',
                'government reporting purposes',
                'self-identification survey',
                'veterans readjustment assistance act',
                'federal contractor or subcontractor',
                'omb control number 1250-0005',
                'expires 04/30/2026',
                'form cc-305',
                'page 1 of 1',
                'completing this form is voluntary',
                'vietnam era veterans readjustment'
            ]

            # If content contains non-job patterns, use full content but mark as failed extraction
            if any(pattern in content_lower for pattern in non_job_patterns):
                logger.warning("Content appears to be a form or redirect, using full content")
                return content.strip(), False

            # Try to extract clean job description
            lines = content.split('\n')
            description_started = False
            description_lines = []

            for line in lines:
                line = line.strip()

                # Skip empty lines but check headers for job description keywords
                if not line:
                    if description_started:
                        description_lines.append(line)
                    continue

                # Look for job description indicators
                if any(keyword in line.lower() for keyword in [
                    'job description', 'about the role', 'what you\'ll do',
                    'responsibilities', 'requirements', 'qualifications',
                    'what we\'re looking for', 'role overview', 'position overview',
                    'about this role', 'key responsibilities', 'job summary',
                    'role summary', 'position summary', 'we are looking for',
                    'the ideal candidate', 'you will be responsible',
                    'about you and the role', 'about the position', 'about this position',
                    'the role', 'this role', 'position details', 'job details',
                    'what you\'ll be doing', 'what you will do', 'key duties',
                    'main responsibilities', 'primary responsibilities'
                ]):
                    description_started = True
                    description_lines.append(line)
                elif description_started and not line.startswith('#'):
                    description_lines.append(line)

            # Clean up the description
            extracted_description = '\n'.join(description_lines).strip()

            # If we found a good extracted description, use it
            if len(extracted_description) >= 100:
                logger.info("Successfully extracted clean job description from Jina AI content")
                return extracted_description, True

            # Fallback to full content if extraction didn't work well
            logger.warning("Jina AI clean description extraction failed, using full content")
            return content.strip(), False

        except Exception as e:
            logger.error(f"Error processing Jina AI content: {e}")
            return content.strip() if content else None, False

    async def _extract_with_playwright_agentql(self, page, job_url: str, job_id: str, job_title: str = None, strategy: str = "simple_agentql") -> Tuple[str, bool, Optional[str], Optional[str]]:
        """
        Extract job description from a single URL using AgentQL with Playwright (async version).
        
        Args:
            page: Playwright page wrapped with AgentQL
            job_url: The job posting URL
            job_id: MongoDB document ID for logging
            job_title: Job title to prepend to descriptions
            strategy: "simple_agentql" or "comprehensive_agentql"
            
        Returns:
            Tuple of (job_id, success, description, error_message)
        """
        if not job_url or not job_url.startswith('http'):
            error_msg = f"Invalid URL: {job_url}"
            logger.warning(f"Invalid URL for job {job_id}: {job_url}")
            return job_id, False, None, error_msg, False
            
        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"Processing job {job_id} (attempt {attempt + 1}/{MAX_RETRIES}) with {strategy}: {job_url}")
                
                # Navigate to the job URL
                await page.goto(job_url, timeout=TIMEOUT, wait_until='domcontentloaded')
                
                # Wait for page to load completely - but don't fail if networkidle times out
                try:
                    await page.wait_for_load_state('load', timeout=10000)
                    logger.debug(f"Job {job_id}: Page 'load' event completed")
                except Exception as e:
                    logger.warning(f"Job {job_id}: Load state wait timed out, continuing anyway: {e}")
                
                # Try to wait for networkidle, but don't fail if it times out
                if WAIT_FOR_NETWORKIDLE:
                    try:
                        await page.wait_for_load_state('networkidle', timeout=NETWORKIDLE_TIMEOUT)
                        logger.debug(f"Job {job_id}: Page reached 'networkidle' state")
                    except Exception as e:
                        logger.warning(f"Job {job_id}: Network idle not achieved (common for sites with analytics), continuing anyway")
                else:
                    logger.debug(f"Job {job_id}: Skipping networkidle wait (WAIT_FOR_NETWORKIDLE=False)")
                
                # Wait for any popups and dismiss them
                await self.handle_popups(page)
                
                # Wait for dynamic content to load
                await asyncio.sleep(3)
                
                # Try to wait for common job description selectors
                try:
                    await page.wait_for_selector('body', timeout=10000)
                    selectors_to_wait = [
                        '[class*="job-description"]', '[class*="description"]', '[class*="content"]',
                        'main', 'article', '.content', '#content'
                    ]
                    for selector in selectors_to_wait:
                        try:
                            await page.wait_for_selector(selector, timeout=2000)
                            break
                        except:
                            continue
                            
                except Exception as e:
                    logger.warning(f"Could not wait for specific selectors for job {job_id}: {e}")
                
                # Scroll the page to trigger lazy-loaded content
                try:
                    logger.info(f"Scrolling page to load dynamic content for job {job_id}")
                    for i in range(3):
                        await page.evaluate('window.scrollBy(0, window.innerHeight)')
                        await asyncio.sleep(0.5)
                    await page.evaluate('window.scrollTo(0, 0)')
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.warning(f"Could not scroll page for job {job_id}: {e}")
                
                # Use AgentQL to extract job description
                try:
                    if not hasattr(page, 'query_data'):
                        raise Exception("AgentQL not properly initialized - page object missing 'query_data' method")
                    
                    description = None
                    if strategy == "simple_agentql":
                        simple_query = """
                        {
                            job_description
                        }
                        """
                        result = await page.query_data(simple_query)
                        if result and 'job_description' in result and result['job_description']:
                            description = result['job_description'].strip()
                            logger.info(f"Simple AgentQL successful for job {job_id}")
                    elif strategy == "comprehensive_agentql":
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
                        result = await page.query_data(comprehensive_query)
                        if result:
                            parts = []
                            for key in ['job_description', 'job_overview', 'about_role', 'responsibilities',
                                        'requirements', 'qualifications', 'main_content']:
                                if key in result and result[key]:
                                    content = result[key].strip()
                                    if content and len(content) > 50:
                                        parts.append(content)

                            if parts:
                                unique_parts = []
                                for part in parts:
                                    is_duplicate = any(part in existing or existing in part for existing in unique_parts)
                                    if not is_duplicate:
                                        unique_parts.append(part)
                                description = '\n\n'.join(unique_parts)
                                logger.info(f"Comprehensive AgentQL successful for job {job_id}")

                    if description and description.strip():
                        if job_title:
                            description = f"# {job_title}\n\n{description.strip()}"
                        
                        is_valid, validation_error = await self.is_valid_description(description, job_id)
                        
                        if is_valid:
                            logger.info(f"✅ Successfully extracted and validated job description for job {job_id}")
                            return job_id, True, description, None, True
                        else:
                            logger.warning(f"⚠️ Job description extracted but failed validation for job {job_id}: {validation_error}")
                            return job_id, False, description, f"Validation failed: {validation_error}", True
                    else:
                        logger.warning(f"⚠️ AgentQL extraction failed for job {job_id} with strategy {strategy}")
                        return job_id, False, None, f"AgentQL extraction failed with strategy {strategy}", False
                        
                except Exception as e:
                    logger.error(f"AgentQL query failed for job {job_id} with strategy {strategy}: {e}")
                    try:
                        await self.check_agentql_error(str(e))
                    except (AgentQLLimitError, AgentQLCriticalError) as agentql_error:
                        raise agentql_error
                    
                    if attempt == MAX_RETRIES - 1:
                        return job_id, False, None, f"AgentQL query failed: {str(e)}", False
                    await asyncio.sleep(2)
                    
            except (AgentQLLimitError, AgentQLCriticalError) as e:
                logger.critical(f"🚨 Critical AgentQL error encountered: {e}")
                raise
            except Exception as e:
                error_msg = f"Exception on attempt {attempt + 1}: {str(e)}"
                logger.error(f"Error processing job {job_id}: {e}")
                try:
                    await self.check_agentql_error(str(e))
                except (AgentQLLimitError, AgentQLCriticalError) as agentql_error:
                    raise agentql_error
                
                if attempt == MAX_RETRIES - 1:
                    return job_id, False, None, error_msg, False
                await asyncio.sleep(2)
        
        error_msg = f"Max retries ({MAX_RETRIES}) exceeded for URL: {job_url}"
        return job_id, False, None, error_msg, False

    async def _extract_with_playwright_direct(self, page, job_url: str, job_id: str, job_title: str = None) -> Tuple[str, bool, Optional[str], Optional[str]]:
        """
        Extract job description from a single URL using direct Playwright (async version).
        
        Args:
            page: Playwright page
            job_url: The job posting URL
            job_id: MongoDB document ID for logging
            job_title: Job title to prepend to descriptions
            
        Returns:
            Tuple of (job_id, success, description, error_message)
        """
        if not job_url or not job_url.startswith('http'):
            error_msg = f"Invalid URL: {job_url}"
            logger.warning(f"Invalid URL for job {job_id}: {job_url}")
            return job_id, False, None, error_msg, False
            
        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"Processing job {job_id} (attempt {attempt + 1}/{MAX_RETRIES}) with direct Playwright: {job_url}")
                
                await page.goto(job_url, timeout=TIMEOUT, wait_until='domcontentloaded')
                
                try:
                    await page.wait_for_load_state('load', timeout=10000)
                except Exception as e:
                    logger.warning(f"Job {job_id}: Load state wait timed out, continuing anyway: {e}")
                
                if WAIT_FOR_NETWORKIDLE:
                    try:
                        await page.wait_for_load_state('networkidle', timeout=NETWORKIDLE_TIMEOUT)
                    except Exception as e:
                        logger.warning(f"Job {job_id}: Network idle not achieved (common for sites with analytics), continuing anyway")
                
                await self.handle_popups(page)
                await asyncio.sleep(3) # Wait for dynamic content
                
                description = await page.locator('body').inner_text()
                
                if description and description.strip():
                    if job_title:
                        description = f"# {job_title}\n\n{description.strip()}"
                    
                    is_valid, validation_error = await self.is_valid_description(description, job_id)
                    
                    if is_valid:
                        logger.info(f"✅ Successfully extracted and validated job description for job {job_id} with direct Playwright")
                        return job_id, True, description, None, True
                    else:
                        logger.warning(f"⚠️ Direct Playwright extraction failed validation for job {job_id}: {validation_error}")
                        return job_id, False, description, f"Validation failed: {validation_error}", True
                else:
                    logger.warning(f"⚠️ Direct Playwright extraction failed for job {job_id}")
                    return job_id, False, None, "Direct Playwright extraction failed", False
                    
            except Exception as e:
                error_msg = f"Exception on attempt {attempt + 1}: {str(e)}"
                logger.error(f"Error processing job {job_id} with direct Playwright: {e}")
                
                if attempt == MAX_RETRIES - 1:
                    return job_id, False, None, error_msg, False
                await asyncio.sleep(2)
        
        error_msg = f"Max retries ({MAX_RETRIES}) exceeded for URL: {job_url}"
        return job_id, False, None, error_msg, False

    async def handle_popups(self, page):
        """Handle common popups that might appear on job pages (async version)"""
        try:
            popup_selectors = [
                '[class*="popup"]', '[class*="modal"]', '[class*="overlay"]',
                '[class*="cookie"]', '[class*="consent"]', '[class*="banner"]',
                '[id*="popup"]', '[id*="modal"]', '[id*="cookie"]',
                '[id*="consent"]', '[id*="banner"]',
                'button[class*="close"]', 'button[class*="dismiss"]',
                'button[class*="accept"]', 'button[class*="decline"]',
                '[aria-label*="close"]', '[aria-label*="dismiss"]',
                '[aria-label*="accept"]', '[aria-label*="decline"]'
            ]
            
            await asyncio.sleep(1) # Wait a bit for popups to appear
            
            for selector in popup_selectors:
                try:
                    popup = await page.query_selector(selector)
                    if popup and await popup.is_visible():
                        logger.info(f"Found popup with selector: {selector}")
                        
                        close_buttons = [
                            'button[class*="close"]', 'button[class*="dismiss"]',
                            'button[class*="accept"]', 'button[class*="decline"]',
                            '[aria-label*="close"]', '[aria-label*="dismiss"]',
                            '[aria-label*="accept"]', '[aria-label*="decline"]',
                            'button', 'a'
                        ]
                        
                        for close_selector in close_buttons:
                            try:
                                close_btn = await popup.query_selector(close_selector)
                                if close_btn and await close_btn.is_visible():
                                    await close_btn.click()
                                    logger.info(f"Clicked close button: {close_selector}")
                                    await asyncio.sleep(1)
                                    break
                            except:
                                continue
                        
                        try:
                            await page.keyboard.press('Escape')
                            logger.info("Pressed Escape to close popup")
                            await asyncio.sleep(1)
                        except:
                            pass
                            
                except Exception as e:
                    continue
                    
        except Exception as e:
            logger.warning(f"Error handling popups: {e}")

    async def extract_job_description(self, page, job_url: str, job_id: str, job_title: str = None) -> Tuple[str, bool, Optional[str], Optional[str], bool]:
        """
        Orchestrates different strategies to extract job description.
        Returns: Tuple of (job_id, success, description, error_message, api_call_success)
        """
        description = None
        error_message = None
        success = False
        api_call_success = False # Indicates if the API call itself was successful (even if validation failed)

        # Strategy 1: Jina AI Extraction
        logger.info(f"Attempting Strategy 1 (Jina AI) for job {job_id}")
        job_id_jina, description_data_jina, api_success_jina, error_message_jina = await self.fetch_job_description_jina_ai(job_url, job_id, job_title)
        
        if api_success_jina and description_data_jina:
            if isinstance(description_data_jina, tuple):
                description, jd_extraction_success = description_data_jina
            else:
                description = description_data_jina
                jd_extraction_success = True # Assume success if old format

            if description and description.strip():
                is_valid, validation_error = await self.is_valid_description(description, job_id)
                
                if is_valid:
                    logger.info(f"Strategy 1 (Jina AI) successful for job {job_id}")
                    return job_id, True, description, None, True
                else:
                    logger.warning(f"Strategy 1 (Jina AI) extracted but failed validation for job {job_id}. Error: {validation_error or 'Validation failed'}")
                    # Store description even if validation failed for debugging
                    return job_id, False, description, validation_error or "Validation failed (Jina AI)", True
            else:
                logger.warning(f"Strategy 1 (Jina AI) extracted empty description for job {job_id}")
                return job_id, False, description or "", error_message_jina or "Empty description (Jina AI)", True
        elif not api_success_jina:
            logger.warning(f"Strategy 1 (Jina AI) failed API call for job {job_id}. Error: {error_message_jina}")
            # If Jina AI API call itself failed, we need to return this immediately to mark as API error in DB
            return job_id, False, None, error_message_jina, False
        else:
            logger.info(f"Strategy 1 (Jina AI) did not yield valid content for job {job_id}")

        # Strategy 2: Simple Playwright Extraction (no AgentQL)
        logger.info(f"Attempting Strategy 2 (Direct Playwright) for job {job_id}")
        job_id_pw, success_pw, description_pw, error_message_pw, api_call_success_pw = await self._extract_with_playwright_direct(page, job_url, job_id, job_title)
        if success_pw:
            logger.info(f"Strategy 2 (Direct Playwright) successful for job {job_id}")
            return job_id_pw, success_pw, description_pw, error_message_pw, api_call_success_pw
        else:
            logger.warning(f"Strategy 2 (Direct Playwright) failed for job {job_id}. Error: {error_message_pw}")

        # Strategy 3: Simple AgentQL Query
        logger.info(f"Attempting Strategy 3 (Simple AgentQL) for job {job_id}")
        job_id_saql, success_saql, description_saql, error_message_saql, api_call_success_saql = await self._extract_with_playwright_agentql(page, job_url, job_id, job_title, strategy="simple_agentql")
        if success_saql:
            logger.info(f"Strategy 3 (Simple AgentQL) successful for job {job_id}")
            return job_id_saql, success_saql, description_saql, error_message_saql, api_call_success_saql
        elif not api_call_success_saql: # AgentQL API call itself failed
            return job_id_saql, success_saql, description_saql, error_message_saql, api_call_success_saql
        else:
            logger.warning(f"Strategy 3 (Simple AgentQL) failed for job {job_id}. Error: {error_message_saql}")

        # Strategy 4: Comprehensive AgentQL Query
        logger.info(f"Attempting Strategy 4 (Comprehensive AgentQL) for job {job_id}")
        job_id_caql, success_caql, description_caql, error_message_caql, api_call_success_caql = await self._extract_with_playwright_agentql(page, job_url, job_id, job_title, strategy="comprehensive_agentql")
        if success_caql:
            logger.info(f"Strategy 4 (Comprehensive AgentQL) successful for job {job_id}")
            return job_id_caql, success_caql, description_caql, error_message_caql, api_call_success_caql
        elif not api_call_success_caql: # AgentQL API call itself failed
            return job_id_caql, success_caql, description_caql, error_message_caql, api_call_success_caql
        else:
            logger.warning(f"Strategy 4 (Comprehensive AgentQL) failed for job {job_id}. Error: {error_message_caql}")
            
        logger.error(f"❌ All extraction strategies failed for job {job_id}")
        return job_id, False, None, "All extraction strategies failed", False

    async def process_batch(self, jobs: List[Dict], browser) -> List[Tuple[str, bool, Optional[str], Optional[str], bool]]:
        """
        Process a batch of jobs concurrently using async Playwright and Jina AI.
        
        Args:
            jobs: List of job documents from MongoDB
            browser: Playwright browser instance
            
        Returns:
            List of (job_id, success, description, error_message, api_call_success) tuples
            
        Raises:
            AgentQLLimitError: If AgentQL API limit is reached
            AgentQLCriticalError: If critical AgentQL error occurs
            JinaAICriticalError: If critical Jina AI error occurs
        """
        results: List[Tuple[str, bool, Optional[str], Optional[str], bool]] = []
        tasks = []

        for job in jobs:
            if self.should_stop:
                logger.warning("⚠️ Stopping batch processing due to previous critical error")
                break

            job_id = str(job['_id'])
            job_url = job.get('job_link', '')
            job_title = job.get('title', '')

            self.job_info[job_id] = {
                'job_url': job_url,
                'job_title': job_title
            }

            if job_url:
                tasks.append(self._process_single_job(browser, job_url, job_id, job_title))
            else:
                self.failed_count += 1
                results.append((job_id, False, None, "Invalid job URL", False))

        if not tasks:
            return results

        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in batch_results:
            if isinstance(res, (AgentQLLimitError, AgentQLCriticalError, JinaAICriticalError)):
                self.should_stop = True
                raise res
            if isinstance(res, Exception):
                logger.error(f"Unexpected error during job processing: {res}")
                self.failed_count += 1
                results.append(("unknown_job_id", False, None, str(res), False))
            else:
                results.append(res)

        return results

    async def _process_single_job(self, browser, job_url: str, job_id: str, job_title: str) -> Tuple[str, bool, Optional[str], Optional[str], bool]:
        """
        Helper to process a single job, including page creation and closing.
        """
        page = None
        try:
            page = await browser.new_page()
            wrapped_page = agentql.wrap(page)
            return await self.extract_job_description(wrapped_page, job_url, job_id, job_title)
        except Exception as e:
            logger.error(f"Error processing single job {job_id}: {e}")
            return job_id, False, None, str(e), False
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
        
    async def update_job_descriptions(self, results: List[Tuple[str, bool, Optional[str], Optional[str], bool]]):
        """
        Update MongoDB with job descriptions (async version)
        
        Args:
            results: List of (job_id, success, description, error_message, api_call_success) tuples
        """
        if not results:
            return
            
        from bson import ObjectId
        
        # Update jobs individually
        for job_id, success, description, error_message, api_call_success in results:
            try:
                if success and description:
                    update_data = {
                        'job_description': description,
                        'jd_extraction': True,
                        'api_error': None,  # Clear any previous API error
                        'retry_error': None, # Clear any previous retry error
                        'retry_extracted_at': datetime.now()
                    }
                    
                    result = await self.collection.update_one(
                        {'_id': ObjectId(job_id)},
                        {'$set': update_data}
                    )
                    
                    if result.modified_count > 0:
                        self.processed_count += 1
                        logger.info(f"✅ Updated job {job_id} with validated description")
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
                        
                elif not api_call_success: # API call itself failed (Jina AI or AgentQL)
                    update_data = {
                        'jd_extraction': False,
                        'api_error': error_message, # Store API error
                        'retry_attempted_at': datetime.now() # Mark retry attempt
                    }
                    
                    result = await self.collection.update_one(
                        {'_id': ObjectId(job_id)},
                        {'$set': update_data}
                    )
                    
                    if result.modified_count > 0:
                        self.failed_count += 1
                        logger.info(f"❌ Marked job {job_id} as failed due to API error (Error: {error_message})")
                        job_info = self.job_info.get(job_id, {})
                        self.results.append({
                            'job_id': job_id,
                            'job_title': job_info.get('job_title', ''),
                            'job_link': job_info.get('job_url', ''),
                            'status': 'api_failed',
                            'description_length': 0,
                            'job_description': '',
                            'error': error_message
                        })
                    else:
                        logger.warning(f"⚠️ No changes made to job {job_id}")

                elif not success and description: # Extraction succeeded but validation failed
                    update_data = {
                        'job_description': description,  # Store the partial extraction
                        'jd_extraction': False,  # Mark as failed
                        'retry_error': error_message, # Store validation error
                        'retry_attempted_at': datetime.now()
                    }
                    
                    result = await self.collection.update_one(
                        {'_id': ObjectId(job_id)},
                        {'$set': update_data}
                    )
                    
                    if result.modified_count > 0:
                        self.failed_count += 1
                        logger.info(f"⚠️ Job {job_id}: Extracted content failed validation, stored for review (Error: {error_message})")
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
                        
                else: # Generic failure (no description, no specific API error, but not successful)
                    update_data = {
                        'jd_extraction': False,
                        'retry_error': error_message or "Unknown extraction failure",
                        'retry_attempted_at': datetime.now()
                    }
                    
                    result = await self.collection.update_one(
                        {'_id': ObjectId(job_id)},
                        {'$set': update_data}
                    )
                    
                    if result.modified_count > 0:
                        self.failed_count += 1
                        logger.info(f"❌ Marked job {job_id} as failed (Error: {error_message or 'Unknown'})")
                        job_info = self.job_info.get(job_id, {})
                        self.results.append({
                            'job_id': job_id,
                            'job_title': job_info.get('job_title', ''),
                            'job_link': job_info.get('job_url', ''),
                            'status': 'failed',
                            'description_length': 0,
                            'job_description': '',
                            'error': error_message or "Unknown extraction failure"
                        })
                    else:
                        logger.warning(f"⚠️ No changes made to job {job_id}")
                        
            except Exception as e:
                logger.error(f"Error updating job {job_id}: {e}")
                self.failed_count += 1

    async def save_results_to_csv(self, filename: str = None):
        """Save extraction results to CSV file (async version)"""
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


    async def run_retry_extraction(self, limit: Optional[int] = None, batch_size: int = BATCH_SIZE):
        """
        Main retry extraction process (async version)
        
        Args:
            limit: Maximum number of jobs to process
            batch_size: Number of jobs to process per batch
        
        Raises:
            AgentQLLimitError: If AgentQL API limit is reached
            AgentQLCriticalError: If critical AgentQL error occurs
            JinaAICriticalError: If critical Jina AI error occurs
        """
        self.start_time = time.time()
        
        try:
            await self.setup_mongodb_connection()
            await self.setup_http_session()
            
            all_jobs = await self.get_failed_jobs(limit)
            
            if not all_jobs:
                logger.info("No jobs found with jd_extraction = False")
                return
            
            logger.info(f"Starting retry extraction for {len(all_jobs)} jobs...")
            
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=HEADLESS)
                
                try:
                    for i in range(0, len(all_jobs), batch_size):
                        if self.should_stop:
                            logger.warning("⚠️ Stopping extraction due to critical error")
                            break
                        
                        batch = all_jobs[i:i + batch_size]
                        batch_num = (i // batch_size) + 1
                        total_batches = (len(all_jobs) + batch_size - 1) // batch_size
                        
                        logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} jobs)")
                        
                        try:
                            results = await self.process_batch(batch, browser)
                            await self.update_job_descriptions(results)
                            
                            elapsed = time.time() - self.start_time
                            rate = (self.processed_count + self.failed_count) / elapsed if elapsed > 0 else 0
                            logger.info(f"Progress: {self.processed_count} processed, {self.failed_count} failed, {rate:.2f} jobs/sec")
                            
                        except (AgentQLLimitError, AgentQLCriticalError, JinaAICriticalError) as e:
                            logger.critical(f"🚨 Critical API error occurred: {e}")
                            logger.critical(f"⚠️ Stopping extraction after processing {self.processed_count + self.failed_count} jobs")
                            self.should_stop = True
                            raise # Re-raise to be caught by outer handler
                        
                        if i + batch_size < len(all_jobs) and not self.should_stop:
                            await asyncio.sleep(2)
                finally:
                    await browser.close()
                
                csv_file = await self.save_results_to_csv()
                
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
        except JinaAICriticalError as e:
            logger.critical(f"🚨 Critical Jina AI error: {e}")
            print(f"\n{'=' * 70}")
            print(f"🚨 CRITICAL ERROR: Jina AI Error")
            print(f"{'=' * 70}")
            print(f"Error: {e}")
            print(f"\nThe script has stopped due to a critical Jina AI error.")
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
            if self.http_session:
                await self.http_session.close()

async def main():
    """Main function"""
    if not os.getenv("AGENTQL_API_KEY"):
        logger.error("❌ AGENTQL_API_KEY not found in environment variables")
        # return # No longer returning early here, allowing Jina AI to run if configured
    
    if not JINAAI_API_KEY:
        logger.warning("⚠️ JINAAI_API_KEY not found in environment variables. Jina AI extraction will be skipped.")
    
    extractor = JobDescriptionDynamicExtractor()
    
    print("\n" + "=" * 70)
    print("Job Description Dynamic Extractor".center(70))
    print("=" * 70)
    print(f"\n📋 Configuration:")
    print(f"  • Headless mode: {HEADLESS}")
    print(f"  • Page load timeout: {TIMEOUT/1000:.0f} seconds")
    print(f"  • Network idle timeout: {NETWORKIDLE_TIMEOUT/1000:.0f} seconds")
    print(f"  • Wait for network idle: {WAIT_FOR_NETWORKIDLE}")
    print(f"  • Max retries per job: {MAX_RETRIES}")
    print(f"  • Default Playwright batch size: {BATCH_SIZE}")
    print(f"  • Jina AI batch size: {JINA_BATCH_SIZE}")
    print(f"  • Retry previously failed: {RETRY_PREVIOUSLY_FAILED}")
    if not RETRY_PREVIOUSLY_FAILED:
        print(f"    (Will only process jobs that have never been retried)")
    else:
        print(f"    (Will process all failed jobs, including previously retried ones)")
    print()
    
    try:
        await extractor.setup_mongodb_connection()
        
        total_failed = await extractor.count_failed_jobs()
        if total_failed > 0:
            print(f"⚠️  Found {total_failed} jobs with jd_extraction = False")
            
            failed_jobs = await extractor.get_failed_jobs(limit=10)
            if failed_jobs:
                print(f"\n📝 Preview of first {len(failed_jobs)} jobs:")
                for i, job in enumerate(failed_jobs[:5], 1):
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
        
        limit_input = input("Enter number of jobs to process (press Enter for all): ").strip()
        limit = int(limit_input) if limit_input else None
        
        batch_input = input(f"Enter batch size for Playwright (default {BATCH_SIZE}): ").strip()
        batch_size = int(batch_input) if batch_input else BATCH_SIZE
        
        print(f"\n{'=' * 70}")
        print(f"🚀 Starting retry extraction...")
        print(f"{'=' * 70}")
        print(f"  • Jobs to process: {limit if limit else f'All ({total_failed})'}")
        print(f"  • Playwright batch size: {batch_size}")
        print(f"  • Jina AI batch size: {JINA_BATCH_SIZE}")
        print(f"  • Headless mode: {HEADLESS}")
        print(f"  • Retry config: RETRY_PREVIOUSLY_FAILED = {RETRY_PREVIOUSLY_FAILED}")
        print(f"{'=' * 70}\n")
        
        await extractor.run_retry_extraction(limit=limit, batch_size=batch_size)
        
    except KeyboardInterrupt:
        logger.info("\n⚠️  Retry extraction interrupted by user")
        print("\n⚠️  Process interrupted by user. Partial results may have been saved.")
    except (AgentQLLimitError, AgentQLCriticalError, JinaAICriticalError) as e:
        # Errors already handled in run_retry_extraction, just exit gracefully
        pass
    except Exception as e:
        logger.error(f"❌ Retry extraction failed: {e}")
        print(f"\n❌ Fatal error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
