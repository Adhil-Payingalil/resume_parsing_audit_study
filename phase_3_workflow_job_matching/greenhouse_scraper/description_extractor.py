import os
import asyncio
import aiohttp
import time
import json
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
        logging.FileHandler(logs_dir / 'description_extractor.log', encoding='utf-8'),
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
                'x-timeout': '60'
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

    async def fetch_job_description(self, job_url: str, job_id: str, job_title: str = None) -> Tuple[str, Optional[str], bool, Optional[str]]:
        """
        Fetch job description from a single URL using Jina AI Reader API
        
        Args:
            job_url: The job posting URL
            job_id: MongoDB document ID for logging
            job_title: Job title to prepend to clean extractions
            
        Returns:
            Tuple of (job_id, description, api_success, error_message) where:
            - api_success: True if API call succeeded, False if API returned error
            - error_message: Error details if API failed, None if succeeded
        """
        if not job_url or not job_url.startswith('http'):
            error_msg = f"Invalid URL: {job_url}"
            logger.warning(f"Invalid URL for job {job_id}: {job_url}")
            return job_id, None, False, error_msg
            
        # Construct Jina AI Reader URL
        jina_url = f"{JINA_BASE_URL}{job_url}"
        
        for attempt in range(MAX_RETRIES):
            try:
                async with self.session.get(jina_url) as response:
                    if response.status == 200:
                        content = await response.text()
                        
                        # Parse the response to extract job description
                        description, jd_extraction_success = self.extract_description_from_content(content)
                        
                        if description:
                            if jd_extraction_success:
                                # Add job title to clean extractions
                                if job_title:
                                    description = f"# {job_title}\n\n{description}"
                                logger.info(f"✅ Successfully extracted clean job description for job {job_id}")
                            else:
                                logger.info(f"✅ Using full Jina AI content for job {job_id} (extraction failed)")
                            return job_id, (description, jd_extraction_success), True, None
                        else:
                            logger.warning(f"⚠️ No description found for job {job_id}")
                            return job_id, None, True, None
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
                            return job_id, None, False, error_msg
                        await asyncio.sleep(1)
                        
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

    def extract_description_from_content(self, content: str) -> tuple[Optional[str], bool]:
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
                logger.info("Successfully extracted clean job description")
                return extracted_description, True
            else:
                # Fallback to full content if extraction didn't work well
                logger.warning("Job description extraction failed, using full content")
                return content.strip(), False
                
        except Exception as e:
            logger.error(f"Error processing content: {e}")
            return content.strip() if content else None, False

    async def process_batch(self, jobs: List[Dict]) -> List[Tuple[str, Optional[str], bool, Optional[str]]]:
        """
        Process a batch of jobs concurrently
        
        Args:
            jobs: List of job documents from MongoDB
            
        Returns:
            List of (job_id, description, api_success, error_message) tuples
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
        
        # Filter out exceptions and return valid results
        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Task failed with exception: {result}")
                self.failed_count += 1
            elif isinstance(result, tuple) and len(result) == 4:
                valid_results.append(result)
        
        return valid_results

    async def update_job_descriptions(self, results: List[Tuple[str, Optional[str], bool, Optional[str]]]):
        """
        Update MongoDB with job descriptions
        
        Args:
            results: List of (job_id, description, api_success, error_message) tuples
        """
        if not results:
            return
            
        from bson import ObjectId
        
        # Update jobs individually to avoid bulk write issues
        for job_id, description_data, api_success, error_message in results:
            try:
                from bson import ObjectId
                
                if description_data and api_success:
                    # API succeeded - handle both old format (string) and new format (tuple)
                    if isinstance(description_data, tuple):
                        description, jd_extraction_success = description_data
                    else:
                        # Backward compatibility for old format
                        description = description_data
                        jd_extraction_success = True
                    
                    # Update MongoDB with both description and extraction flag
                    update_data = {
                        'job_description': description,
                        'jd_extraction': jd_extraction_success,
                        'api_error': None  # Clear any previous error
                    }
                    
                    result = self.collection.update_one(
                        {'_id': ObjectId(job_id)},
                        {'$set': update_data}
                    )
                    
                    if result.modified_count > 0:
                        self.processed_count += 1
                        extraction_status = "clean extraction" if jd_extraction_success else "full content"
                        logger.info(f"✅ Updated job {job_id} with description ({extraction_status})")
                    else:
                        logger.warning(f"⚠️ No changes made to job {job_id}")
                        
                elif not api_success:
                    # API failed - set jd_extraction to false and store error details
                    update_data = {
                        'jd_extraction': False,
                        'api_error': error_message
                    }
                    
                    result = self.collection.update_one(
                        {'_id': ObjectId(job_id)},
                        {'$set': update_data}
                    )
                    
                    if result.modified_count > 0:
                        self.processed_count += 1
                        logger.info(f"❌ Marked job {job_id} as failed (API error: {error_message}) - will not retry")
                    else:
                        logger.warning(f"⚠️ No changes made to job {job_id}")
                else:
                    # No description data but API succeeded (shouldn't happen)
                    self.failed_count += 1
                    logger.warning(f"⚠️ No description data for job {job_id} despite API success")
                    
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

    async def retry_jobs_with_errors(self, job_ids: List[str] = None, limit: Optional[int] = None):
        """
        Retry jobs that previously had API errors by clearing their error status
        
        Args:
            job_ids: Specific job IDs to retry (None for all error jobs)
            limit: Maximum number of jobs to retry (None for all)
        """
        from bson import ObjectId
        
        if job_ids:
            # Retry specific jobs
            query = {'_id': {'$in': [ObjectId(jid) for jid in job_ids]}}
        else:
            # Retry all jobs with API errors
            query = {
                'api_error': {'$exists': True, '$ne': None},
                'jd_extraction': False
            }

        query = self.build_job_query(query)
        
        # Clear the error status to allow retry
        update_data = {
            'api_error': None,
            'jd_extraction': None  # Reset to allow processing
        }
        
        result = self.collection.update_many(query, {'$unset': update_data})
        
        logger.info(f"Cleared error status for {result.modified_count} jobs - ready for retry")
        return result.modified_count

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
                
                # Small delay between batches
                if i + batch_size < len(all_jobs):
                    await asyncio.sleep(1)
            
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

async def main():
    """Main function"""
    if not JINAAI_API_KEY:
        logger.error("❌ JINAAI_API_KEY not found in environment variables")
        return
    
    print("Job Description Extractor")
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
        
        # Check for jobs with API errors
        error_jobs = await extractor.get_jobs_with_api_errors(limit=10)
        if error_jobs:
            print(f"\n⚠️ Found {len(error_jobs)} jobs with API errors:")
            for job in error_jobs[:5]:  # Show first 5
                print(f"  - {job.get('title', 'Unknown')} at {job.get('company', 'Unknown')}")
                print(f"    Error: {job.get('api_error', 'Unknown')}")
            if len(error_jobs) > 5:
                print(f"  ... and {len(error_jobs) - 5} more")
            print()
        
        limit_input = input("Enter number of jobs to process (press Enter for all): ").strip()
        limit = int(limit_input) if limit_input else None
        
        batch_input = input(f"Enter batch size (default {BATCH_SIZE}): ").strip()
        batch_size = int(batch_input) if batch_input else BATCH_SIZE
        
        print(f"\nStarting extraction...")
        print(f"Limit: {limit if limit else 'All jobs'}")
        print(f"Batch size: {batch_size}")
        print(f"Rate limit delay: {RATE_LIMIT_DELAY}s")
        print("-" * 50)
        
        # Diagnostic counts
        total_cycle_jobs = extractor.collection.count_documents(extractor.job_filter)
        print(f"📊 Diagnostic Check:")
        print(f"   - Total jobs found for Cycle {extractor.cycle}: {total_cycle_jobs}")
        
        # Count excluding the 'jd_extraction: False' filter to see if jobs are being hidden
        pending_query = {
            '$and': [
                extractor.job_filter,
                {
                    'job_link': {'$exists': True, '$ne': ''},
                    '$or': [
                        {'job_description': {'$exists': False}},
                        {'job_description': {'$eq': ''}},
                        {'job_description': None}
                    ]
                }
            ]
        }
        pending_count_total = extractor.collection.count_documents(pending_query)
        print(f"   - Jobs without description (Total): {pending_count_total}")
        
        # Count actually eligible (excluding failed attempts)
        eligible_query = extractor.build_job_query({
            'job_link': {'$exists': True, '$ne': ''},
            'jd_extraction': {'$ne': False},
            '$or': [
                {'job_description': {'$exists': False}},
                {'job_description': {'$eq': ''}},
                {'job_description': None}
            ]
        })
        eligible_count = extractor.collection.count_documents(eligible_query)
        print(f"   - Jobs eligible for extraction (excluding previous failures): {eligible_count}")
        
        if eligible_count == 0 and pending_count_total > 0:
            print(f"\n⚠️ NOTE: {pending_count_total} jobs are missing descriptions but are marked as 'failed' (jd_extraction=False).")
            print("   You may want to reset their status to retry them.")
            
        print("-" * 50)
        
        await extractor.run_extraction(limit=limit, batch_size=batch_size)
        
    except KeyboardInterrupt:
        logger.info("Extraction interrupted by user")
    except CriticalAPIError as e:
        logger.error(f"❌ Critical API Error: {e}")
        logger.error("Please check your JINAAI_API_KEY and API usage limits.")
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        raise
    finally:
        if extractor.session:
            await extractor.session.close()
        if extractor.mongo_client:
            extractor.mongo_client.close()

if __name__ == "__main__":
    asyncio.run(main())
