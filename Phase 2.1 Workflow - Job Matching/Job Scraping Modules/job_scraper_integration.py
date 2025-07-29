"""
Job Scraper Integration Module
Integrates the Job_scrapper library with the resume audit study workflow.

# =============================
# Centralized Configuration (User Configurable)
# =============================
CONFIG = {
    "SITE_NAME": ["linkedin"],
    "SEARCH_TERMS": ["Data Analyst", "Project Manager"],
    "LOCATIONS": ["Toronto, ON"],
    "RESULTS_WANTED": 50,
    "JOB_TYPE": None,
    "IS_REMOTE": False,
    "HOURS_OLD": None,
    "COUNTRY_INDEED": "Canada",
    "PROXIES": None,
    "DELAY_SECONDS": 7,
    "VERBOSE": 2,
    "DESCRIPTION_FORMAT": "markdown",
    "EASY_APPLY": False,
    "LINKEDIN_FETCH_DESCRIPTION": False
}
# =============================

"""

import os
import sys
import pandas as pd
import datetime
from typing import List, Dict, Optional
from dotenv import load_dotenv
from pymongo.errors import PyMongoError

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from libs.mongodb import _get_mongo_client
from utils import get_logger
from config_job_scraper import CONFIG

load_dotenv()
logger = get_logger(__name__)

class JobScraperIntegration:
    """
    Integrates job scraping functionality with the resume audit study workflow.
    """
    
    def __init__(self, db_name: str = "Resume_study"):
        self.db_name = db_name
        self.mongo_client = _get_mongo_client()
        if not self.mongo_client:
            raise ConnectionError("Failed to connect to MongoDB")
        
        self.db = self.mongo_client[db_name]
        self.job_postings_collection = self.db["job_postings"]
        
        # Create indexes for performance
        self._create_indexes()
        
        logger.info(f"JobScraperIntegration initialized for database: {db_name}")
    
    def _create_indexes(self):
        """Create necessary indexes for the job_postings collection."""
        try:
            # Remove old unique index on job_link if it exists
            existing_indexes = list(self.job_postings_collection.index_information().keys())
            if "job_link_1" in existing_indexes:
                self.job_postings_collection.drop_index("job_link_1")
                logger.info("Dropped old unique index on job_link")

            # Create unique index for job_url_direct (preferred)
            self.job_postings_collection.create_index("job_url_direct", unique=True, sparse=True)
            logger.info("Created unique index on job_url_direct (sparse)")

            # Create unique index for job_url (as backup)
            self.job_postings_collection.create_index("job_url", unique=True, sparse=True)
            logger.info("Created unique index on job_url (sparse)")

            # Index for status to quickly find pending jobs
            self.job_postings_collection.create_index("status")

            # Index for scraped_at for time-based queries
            self.job_postings_collection.create_index("scraped_at")

            logger.info("Database indexes created successfully")

        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
    
    def scrape_jobs_from_platforms(
        self,
        search_terms: List[str],
        locations: List[str],
        platforms: List[str] = ["indeed", "linkedin"],
        results_per_search: int = 50,
        hours_old: int = 168,  # 1 week
        **kwargs
    ) -> pd.DataFrame:
        """
        Scrape jobs from multiple platforms using the jobspy library.
        
        Args:
            search_terms: List of job search terms
            locations: List of locations to search
            platforms: List of platforms to scrape from
            results_per_search: Number of results per search term
            hours_old: Filter jobs posted within this many hours
            **kwargs: Additional arguments for scrape_jobs
            
        Returns:
            DataFrame containing scraped job data
        """
        try:
            # Import jobspy library
            from jobspy import scrape_jobs
        except ImportError:
            logger.error("jobspy library not found. Please install it using: pip install python-jobspy")
            raise ImportError("jobspy library is required for job scraping")
        
        all_jobs = []
        
        for search_term in search_terms:
            for location in locations:
                logger.info(f"Scraping jobs for '{search_term}' in '{location}'")
                
                try:
                    jobs_df = scrape_jobs(
                        site_name=platforms,
                        search_term=search_term,
                        location=location,
                        results_wanted=results_per_search,
                        hours_old=hours_old,
                        **kwargs
                    )
                    
                    if not jobs_df.empty:
                        # Add metadata
                        jobs_df['search_term'] = search_term
                        jobs_df['search_location'] = location
                        jobs_df['scraped_at'] = datetime.datetime.now()
                        
                        all_jobs.append(jobs_df)
                        logger.info(f"Scraped {len(jobs_df)} jobs for '{search_term}' in '{location}'")
                    else:
                        logger.warning(f"No jobs found for '{search_term}' in '{location}'")
                        
                except Exception as e:
                    logger.error(f"Error scraping jobs for '{search_term}' in '{location}': {e}")
                    continue
        
        if all_jobs:
            combined_df = pd.concat(all_jobs, ignore_index=True)
            logger.info(f"Total jobs scraped: {len(combined_df)}")
            return combined_df
        else:
            logger.warning("No jobs were scraped from any platform")
            return pd.DataFrame()
    
    def clean_and_transform_job_data(self, jobs_df: pd.DataFrame, save_csv: bool = False) -> pd.DataFrame:
        """
        Clean and transform scraped job data to match the MongoDB schema.
        Only keep important columns, fill missing ones, and remove duplicates.
        """
        import numpy as np
        if jobs_df.empty:
            logger.info("No jobs to clean and transform.")
            return jobs_df

        # List of columns to keep (as per user specification)
        columns_to_keep = [
            'site',
            'job_url',
            'job_url_direct',
            'title',
            'company',
            'location',
            'date_posted',
            'job_type',
            'is_remote',
            'emails',
            'description',
            'company_industry',
            'company_url',  # Maybe, so include if present
            'company_num_employees',
            'company_description',
            'search_term',
            'search_location',
            'scraped_at',
        ]

        # Standardize column names if needed (add more mappings as required)
        column_mapping = {
            'job_url': 'job_url',
            'job_url_direct': 'job_url_direct',
            'title': 'title',
            'company': 'company',
            'location': 'location',
            'date_posted': 'date_posted',
            'job_type': 'job_type',
            'is_remote': 'is_remote',
            'emails': 'emails',
            'description': 'description',
            'company_industry': 'company_industry',
            'company_url': 'company_url',
            'company_num_employees': 'company_num_employees',
            'company_description': 'company_description',
            'search_term': 'search_term',
            'search_location': 'search_location',
            'scraped_at': 'scraped_at',
            'site': 'site',
        }
        # Rename columns if needed
        cleaned_df = jobs_df.rename(columns=column_mapping).copy()

        # Ensure all columns to keep are present
        for col in columns_to_keep:
            if col not in cleaned_df.columns:
                cleaned_df[col] = None

        # Select only the columns to keep (in the specified order)
        cleaned_df = cleaned_df[columns_to_keep]

        # Convert date_posted and scraped_at to datetime if present
        for date_col in ['date_posted', 'scraped_at']:
            if date_col in cleaned_df.columns:
                cleaned_df[date_col] = pd.to_datetime(cleaned_df[date_col], errors='coerce')

        # Remove duplicates based on job_url_direct, then job_url if available, else title+company+location
        if 'job_url_direct' in cleaned_df.columns and cleaned_df['job_url_direct'].notna().any():
            cleaned_df = cleaned_df.drop_duplicates(subset=['job_url_direct'])
        elif 'job_url' in cleaned_df.columns and cleaned_df['job_url'].notna().any():
            cleaned_df = cleaned_df.drop_duplicates(subset=['job_url'])
        else:
            cleaned_df = cleaned_df.drop_duplicates(subset=['title', 'company', 'location'])

        # Replace NaT and NaN with None for MongoDB compatibility
        cleaned_df = cleaned_df.where(pd.notnull(cleaned_df), None)

        # Save cleaned DataFrame to CSV for logging (optional)
        if save_csv:
            timestamp_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            csv_filename = f'scraped_jobs_{timestamp_str}.csv'
            cleaned_df.to_csv(csv_filename, index=False)
            logger.info(f"Saved cleaned scraped data to {csv_filename}")

        logger.info(f"Cleaned job data: {len(cleaned_df)} jobs remaining")
        return cleaned_df
    
    def save_jobs_to_mongodb(self, jobs_df: pd.DataFrame) -> int:
        """
        Save cleaned job data to MongoDB.
        Filters out jobs that already exist by job_url_direct or job_url.
        """
        if jobs_df.empty:
            logger.warning("No jobs to save to MongoDB")
            return 0

        jobs_list = jobs_df.to_dict('records')

        # Gather all job_url_direct and job_url values from the batch
        url_directs = set(job['job_url_direct'] for job in jobs_list if job.get('job_url_direct'))
        urls = set(job['job_url'] for job in jobs_list if job.get('job_url'))
        query = {"$or": []}
        if url_directs:
            query["$or"].append({"job_url_direct": {"$in": list(url_directs)}})
        if urls:
            query["$or"].append({"job_url": {"$in": list(urls)}})

        if query["$or"]:
            try:
                existing_jobs = self.job_postings_collection.find(query, {"job_url_direct": 1, "job_url": 1})
                existing_url_directs = set()
                existing_urls = set()
                for job in existing_jobs:
                    if 'job_url_direct' in job and job['job_url_direct']:
                        existing_url_directs.add(job['job_url_direct'])
                    if 'job_url' in job and job['job_url']:
                        existing_urls.add(job['job_url'])
                new_jobs = [job for job in jobs_list if (job.get('job_url_direct') not in existing_url_directs and job.get('job_url') not in existing_urls)]
                logger.info(f"Filtered out {len(jobs_list) - len(new_jobs)} existing jobs by job_url_direct/job_url")
            except Exception as e:
                logger.error(f"Error querying existing jobs: {e}")
                new_jobs = jobs_list
        else:
            new_jobs = jobs_list

        if not new_jobs:
            logger.info("No new jobs to insert")
            return 0

        try:
            # Chunking for large inserts
            chunk_size = 1000
            total_inserted = 0
            inserted_ids = []
            
            for i in range(0, len(new_jobs), chunk_size):
                chunk = new_jobs[i:i+chunk_size]
                result = self.job_postings_collection.insert_many(chunk)
                chunk_ids = result.inserted_ids
                inserted_ids.extend(chunk_ids)
                total_inserted += len(chunk_ids)
                logger.info(f"Inserted chunk {i//chunk_size+1}: {len(chunk_ids)} jobs")
            
            logger.info(f"Successfully saved {total_inserted} new jobs to MongoDB")
            
            # Generate embeddings for new jobs
            if inserted_ids:
                self._generate_embeddings_for_new_jobs(inserted_ids)
            
            return total_inserted

        except Exception as e:
            logger.error(f"Error saving jobs to MongoDB: {e}")
            return 0
    
    def _generate_embeddings_for_new_jobs(self, job_ids: List):
        """
        Generate embeddings for newly inserted job postings.
        
        Args:
            job_ids (List): List of ObjectIds for newly inserted jobs
        """
        try:
            from libs.gemini_processor import GeminiProcessor
            from libs.text_extraction import extract_job_content_from_mongo_doc
            
            # Initialize embedding processor
            embedding_processor = GeminiProcessor(
                model_name="gemini-1.5-flash",
                temperature=0.0,
                enable_google_search=False
            )
            
            logger.info(f"Generating embeddings for {len(job_ids)} new job postings")
            
            successful_embeddings = 0
            failed_embeddings = 0
            
            for job_id in job_ids:
                try:
                    # Get the job document
                    job_doc = self.job_postings_collection.find_one({"_id": job_id})
                    if not job_doc:
                        logger.warning(f"Job document not found for ID: {job_id}")
                        failed_embeddings += 1
                        continue
                    
                    # Extract content for embedding
                    content = extract_job_content_from_mongo_doc(job_doc)
                    if not content:
                        logger.warning(f"No content extracted for job: {job_doc.get('job_title', 'unknown')}")
                        failed_embeddings += 1
                        continue
                    
                    # Generate embedding
                    embedding = embedding_processor.generate_embedding(
                        text=content,
                        task_type="RETRIEVAL_QUERY"
                    )
                    
                    if not embedding:
                        logger.error(f"Failed to generate embedding for job: {job_doc.get('job_title', 'unknown')}")
                        failed_embeddings += 1
                        continue
                    
                    # Update document with embedding
                    result = self.job_postings_collection.update_one(
                        {"_id": job_id},
                        {
                            "$set": {
                                "jd_embedding": embedding,
                                "embedding_generated_at": datetime.datetime.now(),
                                "embedding_model": "embedding-001",
                                "embedding_task_type": "RETRIEVAL_QUERY"
                            }
                        }
                    )
                    
                    if result.modified_count > 0:
                        logger.info(f"Successfully generated embedding for job: {job_doc.get('job_title', 'unknown')}")
                        successful_embeddings += 1
                    else:
                        logger.warning(f"Failed to update job with embedding: {job_doc.get('job_title', 'unknown')}")
                        failed_embeddings += 1
                
                except Exception as e:
                    logger.error(f"Error generating embedding for job ID {job_id}: {e}")
                    failed_embeddings += 1
            
            logger.info(f"Embedding generation completed. Successful: {successful_embeddings}, Failed: {failed_embeddings}")
            
        except Exception as e:
            logger.error(f"Error in embedding generation for new jobs: {e}")
    
    def get_pending_jobs(self, limit: int = 100) -> List[Dict]:
        """
        Retrieve pending jobs from MongoDB for processing.
        
        Args:
            limit: Maximum number of jobs to retrieve
            
        Returns:
            List of pending job documents
        """
        try:
            pending_jobs = list(
                self.job_postings_collection.find(
                    {"status": "PENDING"},
                    limit=limit
                )
            )
            logger.info(f"Retrieved {len(pending_jobs)} pending jobs from MongoDB (limit={limit})")
            return pending_jobs
            
        except PyMongoError as e:
            logger.error(f"PyMongoError retrieving pending jobs: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error retrieving pending jobs: {e}")
            return []
    
    def update_job_status(self, job_id: str, status: str, **kwargs):
        """
        Update the status of a job posting.
        
        Args:
            job_id: MongoDB ObjectId of the job
            status: New status
            **kwargs: Additional fields to update
        """
        try:
            update_data = {"status": status, **kwargs}
            self.job_postings_collection.update_one(
                {"_id": job_id},
                {"$set": update_data}
            )
            logger.info(f"Updated job status in MongoDB: job_id={job_id}, status={status}")
            
        except PyMongoError as e:
            logger.error(f"PyMongoError updating job status for job_id={job_id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error updating job status for job_id={job_id}: {e}")
    
    def get_job_statistics(self) -> Dict:
        """
        Get statistics about jobs in the database.
        
        Returns:
            Dictionary with job statistics
        """
        try:
            total_jobs = self.job_postings_collection.count_documents({})
            pending_jobs = self.job_postings_collection.count_documents({"status": "PENDING"})
            processed_jobs = self.job_postings_collection.count_documents({"status": {"$ne": "PENDING"}})
            
            # Get jobs by platform
            platform_stats = {}
            platforms = self.job_postings_collection.distinct("source_platform")
            for platform in platforms:
                count = self.job_postings_collection.count_documents({"source_platform": platform})
                platform_stats[platform] = count
            
            return {
                "total_jobs": total_jobs,
                "pending_jobs": pending_jobs,
                "processed_jobs": processed_jobs,
                "by_platform": platform_stats,
                "last_updated": datetime.datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting job statistics: {e}")
            return {"error": str(e)}

# Example usage and testing
if __name__ == "__main__":
    # Initialize the scraper
    scraper = JobScraperIntegration()
    config = CONFIG
    # Define search parameters from config
    search_terms = config["SEARCH_TERMS"]
    locations = config["LOCATIONS"]
    platforms = config["SITE_NAME"]
    results_per_search = config["RESULTS_WANTED"]
    job_type = config["JOB_TYPE"]
    is_remote = config["IS_REMOTE"]
    hours_old = config["HOURS_OLD"]
    country_indeed = config["COUNTRY_INDEED"]
    proxies = config["PROXIES"]
    verbose = config["VERBOSE"]
    description_format = config["DESCRIPTION_FORMAT"]
    easy_apply = config["EASY_APPLY"]
    linkedin_fetch_description = config["LINKEDIN_FETCH_DESCRIPTION"]
    print("Starting job scraping with centralized config...")
    jobs_df = scraper.scrape_jobs_from_platforms(
        search_terms=search_terms,
        locations=locations,
        platforms=platforms,
        results_per_search=results_per_search,
        job_type=job_type,
        is_remote=is_remote,
        hours_old=hours_old,
        country_indeed=country_indeed,
        proxies=proxies,
        verbose=verbose,
        description_format=description_format,
        easy_apply=easy_apply,
        linkedin_fetch_description=linkedin_fetch_description
    )
    if not jobs_df.empty:
        print(f"Scraped {len(jobs_df)} jobs. Cleaning and saving...")
        cleaned_df = scraper.clean_and_transform_job_data(jobs_df, save_csv=False)
        saved_count = scraper.save_jobs_to_mongodb(cleaned_df)
        print(f"Successfully saved {saved_count} jobs to MongoDB")
        stats = scraper.get_job_statistics()
        print("Job Statistics:", stats)
    else:
        print("No jobs were scraped") 