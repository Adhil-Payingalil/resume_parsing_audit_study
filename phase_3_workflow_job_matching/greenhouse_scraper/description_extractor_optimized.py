import os
import asyncio
import aiohttp
import time
import json
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, DuplicateKeyError
from dotenv import load_dotenv
import logging

class CriticalAPIError(Exception):
    """Custom exception for critical Jina AI API errors (e.g., invalid key, persistent rate limits)."""
    pass

# Load environment variables
load_dotenv()

# Configure logging
from pathlib import Path
from config import (
    LOGS_DIR, JINAAI_API_KEY, MONGODB_URI, MONGODB_DATABASE, 
    MONGODB_COLLECTION, JINA_BASE_URL, RATE_LIMIT_DELAY, 
    BATCH_SIZE, MAX_RETRIES, TIMEOUT, DEFAULT_JOB_FILTER
)

# Create logs directory if it doesn't exist
logs_dir = Path(LOGS_DIR)
logs_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(logs_dir / 'description_extractor_optimized.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# MongoDB job selection filter configuration
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

class JobDescriptionExtractor:
    """
    Handles the extraction of job descriptions from job URLs using Jina AI Reader.
    
    Attributes:
        cycle (float): The scraping cycle number to filter jobs by.
        mongo_client: MongoDB client instance.
        collection: MongoDB collection instance.
        session: aiohttp session for making API requests.
    """
    
    def __init__(self, cycle: float = 0):
        """
        Initialize the extractor with a specific cycle number.
        
        Args:
            cycle (float): The cycle number to identify which batch of jobs to process. 
                           Defaults to 0 (or config default).
        """
        self.mongo_client = None
        self.collection = None
        self.session = None
        self.processed_count = 0
        self.failed_count = 0
        self.start_time = None
        self.cycle = cycle
        
        # Load default filter from config but override cycle
        self.job_filter = DEFAULT_JOB_FILTER.copy()
        self.job_filter['cycle'] = self.cycle
        
    async def setup_mongodb_connection(self):
        """
        Establish connection to MongoDB using environment variables.
        
        Raises:
            Exception: If MONGODB_URI is missing or connection fails.
        """
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
        """
        Initialize aiohttp ClientSession with optimized settings for Jina AI API.
        
        Configures:
        - Connection pooling (limit=100)
        - Timeouts (aligned with Jina AI limits)
        - Default headers (API Key, User-Agent)
        """
        connector = aiohttp.TCPConnector(
            limit=100,  # Total connection pool size
            limit_per_host=30,  # Per-host connection limit
            ttl_dns_cache=300,  # DNS cache TTL
            use_dns_cache=True,
        )
        
        # Timeout configuration aligned with Jina AI's processing time
        timeout = aiohttp.ClientTimeout(
            total=TIMEOUT,      # 60 seconds total
            connect=10,         # 10 seconds to establish connection
            sock_read=TIMEOUT   # 60 seconds to read response
        )
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                'Authorization': f'Bearer {JINAAI_API_KEY}',
                'User-Agent': 'Job-Description-Extractor/1.0',
                'X-Wait-For-Selector': 'body, main, .content, .job-description, [role="main"]',
                'X-Wait-For-Timeout': '5000',
                'x-timeout': '60',
                # 'Accept-cached-content-if-younger-than': '86400', # User disabled cache
                # 'x-retain-images': 'none' # REMOVED: Potentially causing timeouts
            }
        )

    def build_job_query(self, base_query: Dict) -> Dict:
        """
        Combine a base MongoDB query with the configured job filter (cycle, etc.).
        
        Args:
            base_query (Dict): The specific query criteria (e.g., missing description).
            
        Returns:
            Dict: The combined MongoDB query.
        """
        if not self.job_filter:
            return base_query
            
        return {
            '$and': [
                self.job_filter,
                base_query
            ]
        }

    async def fetch_job_description(self, job_url: str, job_id: str, job_title: str = None) -> Tuple[str, str, str, bool, Optional[str]]:
        """
        Fetch job description from a single URL using Jina AI Reader API
        
        Args:
            job_url: The job posting URL
            job_id: MongoDB document ID for logging
            job_title: Job title to prepend to clean extractions and use as start marker
            
        Returns:
            Tuple of (job_id, description, extraction_method, raw_content, api_success, error_message) where:
            - description: The cleaned description (or full content if fallback)
            - extraction_method: "clean", "fallback", or "full_page_content"
            - raw_content: The original content returned by Jina AI
            - api_success: True if API call succeeded
            - error_message: None if succeeded
            
        Raises:
            CriticalAPIError: If API calls fail after all retries
        """
        if not job_url or not job_url.startswith('http'):
            error_msg = f"Invalid URL: {job_url}"
            logger.warning(f"Invalid URL for job {job_id}: {job_url}")
            return job_id, None, None, None, False, error_msg
            
        # Construct Jina AI Reader URL
        jina_url = f"{JINA_BASE_URL}{job_url}"
        
        for attempt in range(MAX_RETRIES):
            try:
                async with self.session.get(jina_url) as response:
                    if response.status == 200:
                        content = await response.text()
                        
                        # Parse the response to extract job description
                        description, extraction_method = self.extract_description_from_content(content, job_title)
                        
                        if description:
                            if extraction_method == "clean":
                                logger.info(f"✅ Successfully extracted clean job description for job {job_id}")
                            elif extraction_method == "fallback":
                                logger.info(f"⚠️ Clean extraction fallback for job {job_id}")
                            else:
                                logger.info(f"⚠️ Using full Jina AI content for job {job_id} (extraction failed)")
                            
                            return job_id, description, extraction_method, content, True, None
                        else:
                            logger.warning(f"⚠️ No description found for job {job_id}")
                            return job_id, None, None, content, True, None
                    elif response.status == 429:
                        # Rate limited - wait longer
                        if attempt == MAX_RETRIES - 1: # Last attempt failed due to rate limit
                            logger.critical(f"❌ Persistent rate limiting (429) for job {job_id}. Max retries exceeded. Stopping extraction.")
                            raise CriticalAPIError(f"Persistent rate limiting (429) after {MAX_RETRIES} attempts for URL: {job_url}")
                        
                        wait_time = (2 ** attempt) * 2  # Exponential backoff
                        logger.warning(f"Rate limited for job {job_id}, waiting {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    elif response.status == 401:
                        # Unauthorized - API key issue
                        logger.critical(f"❌ Jina AI API Unauthorized (401) for job {job_id}. Check API key. Stopping extraction.")
                        raise CriticalAPIError(f"Jina AI API Unauthorized (401). Check JINAAI_API_KEY.")
                    else:
                        error_msg = f"HTTP {response.status} error for URL: {job_url}"
                        logger.error(f"HTTP {response.status} for job {job_id}: {job_url}")
                        if attempt == MAX_RETRIES - 1:
                            # Max retries exceeded for HTTP error - Log and return failure
                            logger.error(f"❌ Persistent HTTP {response.status} for job {job_id}. Marking as failed.")
                            return job_id, None, None, None, False, error_msg
                        await asyncio.sleep(1)
                        
            except asyncio.TimeoutError:
                error_msg = f"Timeout after {MAX_RETRIES} attempts for URL: {job_url}"
                logger.warning(f"Timeout for job {job_id} (attempt {attempt + 1})")
                if attempt == MAX_RETRIES - 1:
                   logger.error(f"❌ Persistent Timeout for job {job_id}. Marking as failed.")
                   return job_id, None, None, None, False, error_msg # Return failure instead of raising CriticalAPIError
                await asyncio.sleep(2 ** attempt)
                
            except CriticalAPIError:
                raise
            except Exception as e:
                error_msg = f"Exception after {MAX_RETRIES} attempts: {str(e)} for URL: {job_url}"
                logger.error(f"Error fetching job {job_id}: {e}")
                if attempt == MAX_RETRIES - 1:
                    logger.error(f"❌ Persistent Error ({type(e).__name__}) for job {job_id}. Marking as failed.")
                    return job_id, None, None, None, False, error_msg # Return failure instead of raising CriticalAPIError
                await asyncio.sleep(1)
        
        # This point should not be reached if handled properly above, but as a safeguard:
        return job_id, None, None, None, False, f"Max retries ({MAX_RETRIES}) exceeded for URL: {job_url}"

    def extract_description_from_content(self, content: str, job_title: str = None) -> tuple[Optional[str], str]:
        """
        Extract job description from Jina AI response content with robust state machine logic.
        
        Args:
            content: Raw content from Jina AI API
            job_title: Job title to use as a potential start marker
            
        Returns:
            Tuple of (extracted_description, extraction_method)
            - extraction_method: "clean", "fallback", or "full_page_content"
        """
        try:
            if not content or len(content.strip()) == 0:
                return None, "full_page_content"
            
            # Check for common non-job content patterns (forms, redirects)
            content_lower = content.lower()
            
            # Pre-validation truncation: 
            # Cut off content at known footer/form markers to prevent their contents (like EEO statements) 
            # from triggering the non-job block.
            validation_content = content_lower
            validation_truncation_markers = [
                "voluntary self-identification",
                "create a job alert",
                "candidate privacy notice"
            ]
            
            for marker in validation_truncation_markers:
                idx = validation_content.find(marker)
                if idx != -1:
                    # Keep only the part before the marker
                    validation_content = validation_content[:idx]

            non_job_patterns = [
                # 'equal employment opportunity policy', # Too broad, appears in footers
                'government reporting purposes',
                'self-identification survey',
                # 'veterans readjustment assistance act', # Too broad
                # 'federal contractor or subcontractor', # Too broad
                'omb control number 1250-0005', # Specific to forms
                'expires 04/30/2026', # Specific to forms
                'form cc-305',
                'page 1 of 1',
                'completing this form is voluntary',
                # 'vietnam era veterans readjustment', # Too broad
                # 'voluntary self-identification', # Too broad
                # 'disability status', # Too broad
                # 'protected veteran', # Too broad (appears in EEO statements)
                'pay transparency non-discrimination provision'
            ]
            
            # If content contains non-job patterns significantly, marker as such
            # Only block if we are SURE it's a form/survey and NOT a job description.
            # EEO statements are common in JDs, so specific form identifiers (like OMB numbers) are safer.
            if any(pattern in validation_content for pattern in non_job_patterns):
                logger.warning("Content identified as a form/survey/redirect (blocked)")
                return None, "full_page_content"  # This ensures jd_extraction=False

            lines = content.split('\n')
            
            # --- Markers Setup ---
            
            # Start Markers
            start_keywords = [
                'about the role', 'what you\'ll do', 'responsibilities', 'requirements', 
                'qualifications', 'what we\'re looking for', 'role overview', 'position overview',
                'about this role', 'key responsibilities', 'job summary', 'role summary',
                'position summary', 'we are looking for', 'the ideal candidate', 
                'you will be responsible', 'about you and the role', 'about the position', 
                'about this position', 'the role', 'this role', 'position details', 'job details',
                'what you\'ll be doing', 'what you will do', 'key duties', 
                'main responsibilities', 'primary responsibilities',
                'who we are', 'about us', 'about the company', 'company overview',
                'location:', 'why join', 'why work', 'why us'
            ]
            
            # Start lines that might begin with "At [Company]" or "Why [Company]"
            # We handle these by checking starts_with in the loop or adding general patterns here.
            # "location:" is a strong signal if it appears early.

            
            # Exact match start markers (case insensitive, strip)
            # "Apply" is often a button/link text that appears right before the description in some layouts
            exact_start_markers = ["apply"]
            
            # End Markers
            end_markers = [
                "create a job alert",
                "apply for this job",
                "voluntary self-identification",
                "privacy policy",
                "candidate privacy notice",
                "submit application",
                "apply now"
            ]
            
            # --- State Machine ---
            # States: SEARCHING -> EXTRACTING -> STOPPED
            
            description_lines = []
            extracted = False
            state = "SEARCHING" # SEARCHING, EXTRACTING, STOPPED
            
            # Cleaning function for fuzzy matching
            def simplify_line(line):
                return re.sub(r'[^a-z0-9]', '', line.lower())
            
            simplified_title = simplify_line(job_title) if job_title else None
            
            start_index = -1
            end_index = -1

            for i, line in enumerate(lines):
                line_stripped = line.strip()
                if not line_stripped:
                    # Keep empty lines only if we are extracting (to preserve paragraphs)
                    if state == "EXTRACTING":
                        description_lines.append(line)
                    continue
                
                line_lower = line_stripped.lower()
                
                # CHECK FOR END MARKERS (Priority Check to stop early)
                # We check this in both SEARCHING and EXTRACTING states
                # If we find an end marker in SEARCHING, it might mean we missed the start 
                # or the intro was very short.
                is_end = False
                for marker in end_markers:
                    if marker in line_lower:
                        # Special check: "Apply" is both a start and part of "Apply for this job"
                        # If the line is EXACTLY "Apply", treat as start (or ignored if extracting)
                        # If "Apply for this job", treat as END.
                        if line_lower == "apply" and "apply" in exact_start_markers:
                            # It's a start marker, not an end marker here
                            break 
                        
                        is_end = True
                        break
                
                if is_end:
                    if state == "EXTRACTING":
                        state = "STOPPED"
                        end_index = i
                        break # Stop processing lines
                    elif state == "SEARCHING":
                        # We hit the end before finding a start. 
                        # We will handle "Fallback" later (take content from 0 to here)
                        end_index = i
                        break
                
                # STATE: SEARCHING
                if state == "SEARCHING":
                    found_start = False
                    
                    # 1. Check Job Title (Fuzzy)
                    if simplified_title:
                        sim_line = simplify_line(line_stripped)
                        if simplified_title in sim_line and len(sim_line) < len(simplified_title) + 20:
                             # It's likely the title header
                            found_start = True
                    
                    # 2. Check "Apply" exact match
                    if not found_start:
                        if line_lower in exact_start_markers:
                            found_start = True
                            
                    # 3. Check Section Keywords
                    if not found_start:
                         if any(keyword in line_lower for keyword in start_keywords):
                             # Ensure it's likely a header (length check or starts with #)
                             if len(line_stripped) < 100 or line_stripped.startswith('#'):
                                 found_start = True
                    
                    # 4. Check "At [Company]" or "Why [Company]" patterns
                    # Many JDs start with "At CompanyName, we..." or "Why CompanyName:"
                    if not found_start:
                        if line_stripped.startswith("At ") or line_stripped.startswith("Why "):
                             # Simple heuristic: if it looks like a sentence start or header about the company
                             # "At SMCP, we embody..." -> len > 20
                             # "Why SMCP:" -> len < 50
                             if len(line_stripped) < 100 or line_stripped.strip().endswith(':'):
                                 found_start = True
                             # Also if it's "At [Company]..." and fairly long, it might be the intro paragraph start
                             elif line_stripped.startswith("At ") and "we " in line_lower:
                                 found_start = True

                    if found_start:
                        state = "EXTRACTING"
                        extracted = True
                        start_index = i
                        # If the start marker is the title or a header, we usually want to include it.
                        # If it's "Apply", we might NOT want to include "Apply" itself if it's a button text.
                        # For now, let's include it, but we can refine.
                        if line_lower not in ["apply"]:
                             description_lines.append(line)
                        continue # Move to next line

                # STATE: EXTRACTING
                elif state == "EXTRACTING":
                    # Skip common button text that might appear in the middle of description
                    if line_lower in ["apply", "apply now", "please apply"]:
                        continue
                    
                    # Remove markdown image links (e.g. ![alt](url))
                    # We use regex to replace them with empty string
                    line_no_images = re.sub(r'!\[.*?\]\(.*?\)', '', line).strip()
                    
                    if line_no_images:
                        # Remove [Back to jobs] links
                        if "[Back to jobs]" in line_no_images:
                             line_no_images = line_no_images.replace("[Back to jobs]", "")
                             # Clean up any leftover url parts if they were attached tightly
                             line_no_images = re.sub(r'\(http.*?\)', '', line_no_images).strip()
                        
                        if line_no_images:
                            description_lines.append(line_no_images)

            # --- Result Processing ---
            
            clean_text = '\n'.join(description_lines).strip()
            
            if extracted and len(clean_text) > 100:
                # Add title if provided and not already likely there
                if job_title and job_title.lower() not in clean_text.lower()[:200]:
                    clean_text = f"# {job_title}\n\n{clean_text}"
                return clean_text, "clean"
            
            # Fallback Logic
            # If we didn't find a start marker, but we found an end marker
            if not extracted and end_index > 0:
                # Take everything from start to end marker
                # We might want to skip the first few lines if they are nav links
                fallback_lines = lines[:end_index]
                fallback_text = '\n'.join(fallback_lines).strip()
                if len(fallback_text) > 100:
                    return fallback_text, "fallback"

            # If cleaned text is too short or logic failed completely
            logger.warning("Job description extraction failed to find markers, using full content")
            return content.strip(), "full_page_content"
                
        except Exception as e:
            logger.error(f"Error processing content: {e}")
            return content.strip() if content else None, "full_page_content"

    async def process_batch(self, jobs: List[Dict]) -> List[Tuple[str, Optional[str], str, str, bool, Optional[str]]]:
        """
        Process a batch of jobs concurrently
        
        Args:
            jobs: List of job documents from MongoDB
            
        Returns:
            List of (job_id, description, extraction_method, raw_content, api_success, error_message) tuples
        """
        tasks = []
        
        for job in jobs:
            job_id = str(job['_id'])
            job_url = job.get('job_link', '')
            job_title = job.get('title', '')
            
            if job_url:
                task = self.fetch_job_description(job_url, job_id, job_title)
                tasks.append(task)
                
                # Add small delay to respect rate limits
                await asyncio.sleep(RATE_LIMIT_DELAY)
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check for CriticalAPIErrors first
        for result in results:
            if isinstance(result, CriticalAPIError):
                raise result
        
        # Filter out other exceptions and return valid results
        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Task failed with exception: {result}")
                self.failed_count += 1
            elif isinstance(result, tuple) and len(result) == 6:
                valid_results.append(result)
        
        return valid_results

    async def update_job_descriptions(self, results: List[Tuple[str, Optional[str], str, str, bool, Optional[str]]]):
        """
        Update MongoDB with job descriptions. 
        Note: ONLY updates successful extractions. Failed extractions stop the script before this point.
        
        Args:
            results: List of (job_id, description, extraction_method, raw_content, api_success, error_message) tuples
        """
        if not results:
            return
            
        from bson import ObjectId
        
        # Update jobs individually to avoid bulk write issues
        for job_id, description, extraction_method, raw_content, api_success, error_message in results:
            try:
                if api_success:
                    # Determine success flag based on method
                    # User requested that fallback/failures be marked as False
                    jd_extraction_success = (extraction_method == "clean")
                    
                    # Update MongoDB with description, extraction method, and raw content
                    update_data = {
                        'job_description': description, # The "best" description we have
                        'jd_extraction': jd_extraction_success, 
                        'jd_extraction_method': extraction_method, # "clean", "fallback", "full_page_content"
                        'jina_raw_content': raw_content, # NEW: Full raw content for audit
                        'api_error': None  # Clear any previous error
                    }
                    
                    result = self.collection.update_one(
                        {'_id': ObjectId(job_id)},
                        {'$set': update_data}
                    )
                    
                    if result.modified_count > 0:
                        self.processed_count += 1
                        logger.info(f"✅ Updated job {job_id} ({extraction_method})")
                    else:
                        logger.warning(f"⚠️ No changes made to job {job_id}")
                        
                else:
                    if not api_success:
                         logger.warning(f"⚠️ Skipping update for job {job_id} due to API failure")
                    
            except Exception as e:
                logger.error(f"Error updating job {job_id}: {e}")
                self.failed_count += 1

    async def get_jobs_without_descriptions(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Get jobs from MongoDB that don't have descriptions yet
        
        Args:
            limit: Maximum number of jobs to process (None for all)
            
        Returns:
            List of job documents
        """
        # Using the same logic as before, but potentially we could use this to re-process 
        # jobs that have 'full_page_content' if we wanted to improve them. 
        # For now, stick to missing descriptions.
        query = {
            'job_link': {'$exists': True, '$ne': ''},
            'jd_extraction': {'$ne': False},  # Exclude jobs that failed API calls
            '$or': [
                {'job_description': {'$exists': False}},
                {'job_description': {'$eq': ''}},
                {'job_description': None}
            ]
        }

        query = self.build_job_query(query)
        
        cursor = self.collection.find(query, {'_id': 1, 'job_link': 1, 'title': 1, 'company': 1})
        
        if limit:
            jobs = list(cursor.limit(limit))
        else:
            jobs = list(cursor)
        
        logger.info(f"Found {len(jobs)} jobs without descriptions")
        return jobs

    async def get_jobs_with_api_errors(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Get jobs from MongoDB that have API errors for reference/retry
        
        Args:
            limit: Maximum number of jobs to retrieve (None for all)
            
        Returns:
            List of job documents with API errors
        """
        query = {
            'api_error': {'$exists': True, '$ne': None},
            'jd_extraction': False
        }

        query = self.build_job_query(query)
        
        cursor = self.collection.find(query, {
            '_id': 1, 
            'job_link': 1, 
            'title': 1, 
            'company': 1, 
            'api_error': 1,
            'created_at': 1
        }).sort('created_at', -1)  # Most recent first
        
        if limit:
            jobs = list(cursor.limit(limit))
        else:
            jobs = list(cursor)
        
        logger.info(f"Found {len(jobs)} jobs with API errors")
        return jobs

    async def run_extraction(self, limit: Optional[int] = None, batch_size: int = BATCH_SIZE):
        """
        Main extraction process
        
        Args:
            limit: Maximum number of jobs to process
            batch_size: Number of jobs to process concurrently
        """
        self.start_time = time.time()
        
        try:
            # Setup connections
            await self.setup_mongodb_connection()
            await self.setup_http_session()
            
            # Get jobs without descriptions
            all_jobs = await self.get_jobs_without_descriptions(limit)
            
            if not all_jobs:
                logger.info("No jobs found that need descriptions")
                return
            
            logger.info(f"Starting extraction for {len(all_jobs)} jobs...")
            
            # Process jobs in batches
            for i in range(0, len(all_jobs), batch_size):
                batch = all_jobs[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = (len(all_jobs) + batch_size - 1) // batch_size
                
                logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} jobs)")
                
                # Process batch
                try:
                    results = await self.process_batch(batch)
                except CriticalAPIError as e:
                    logger.critical(f"Critical API error encountered: {e}. Stopping extraction.")
                    # Re-raise to ensure main function catches it and exits cleanly
                    raise 
                
                # Update MongoDB
                await self.update_job_descriptions(results)
                
                # Progress update
                elapsed = time.time() - self.start_time
                rate = (self.processed_count + self.failed_count) / elapsed if elapsed > 0 else 0
                logger.info(f"Progress: {self.processed_count} processed, {self.failed_count} failed, {rate:.2f} jobs/sec")
                
                # Small delay between batches (Removed as per user request for speed)
                # if i + batch_size < len(all_jobs):
                #     await asyncio.sleep(RATE_LIMIT_DELAY)
            
                # Small delay between batches to prevent sustained rate limiting
            if i + batch_size < len(all_jobs):
                logger.info(f"Sleeping 2s between batches...")
                await asyncio.sleep(2)
        
        # Final summary
            total_time = time.time() - self.start_time
            logger.info(f"✅ Extraction completed!")
            logger.info(f"📊 Total processed: {self.processed_count}")
            logger.info(f"❌ Total failed: {self.failed_count}")
            logger.info(f"⏱️ Total time: {total_time:.2f} seconds")
            logger.info(f"🚀 Average rate: {(self.processed_count + self.failed_count) / total_time:.2f} jobs/sec")
            
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            raise
        finally:
            if self.session:
                await self.session.close()

async def main():
    """Main function"""
    if not JINAAI_API_KEY:
        logger.error("❌ JINAAI_API_KEY not found in environment variables")
        return
    
    print("Job Description Extractor (Optimized)")
    print("=" * 50)
    
    # Get cycle input
    default_cycle = DEFAULT_JOB_FILTER.get('cycle', 0)
    print(f"\nDefault Cycle Number: {default_cycle}")
    cycle_input = input(f"Enter Cycle Number (default {default_cycle}): ").strip()
    
    try:
        cycle = float(cycle_input) if cycle_input else default_cycle
        # If it's effectively an integer, convert for cleanliness
        if cycle.is_integer():
             cycle = int(cycle)
    except ValueError:
        print(f"Invalid input. Using default cycle: {default_cycle}")
        cycle = default_cycle
        
    print(f"Using Cycle Number: {cycle}")
    
    extractor = JobDescriptionExtractor(cycle=cycle)
    
    try:
        # Setup MongoDB connection first
        await extractor.setup_mongodb_connection()
        
        limit_input = input("Enter number of jobs to process (press Enter for all): ").strip()
        limit = int(limit_input) if limit_input else None
        
        batch_input = input(f"Enter batch size (default {BATCH_SIZE}): ").strip()
        batch_size = int(batch_input) if batch_input else BATCH_SIZE
        
        print(f"\nStarting extraction...")
        print(f"Limit: {limit if limit else 'All jobs'}")
        print(f"Batch size: {batch_size}")
        print(f"Rate limit delay: {RATE_LIMIT_DELAY}s")
        print("-" * 50)
        
        await extractor.run_extraction(limit=limit, batch_size=batch_size)
        
    except KeyboardInterrupt:
        logger.info("Extraction interrupted by user")
    except CriticalAPIError as e:
        logger.error(f"❌ Critical API Error: {e}")
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        raise
    finally:
        if extractor.mongo_client:
            extractor.mongo_client.close()

if __name__ == "__main__":
    asyncio.run(main())
