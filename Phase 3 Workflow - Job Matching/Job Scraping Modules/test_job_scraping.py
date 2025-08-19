"""
Test script for job scraping functionality.
This script tests the job scraper integration with a small sample.

"""

import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config_job_scraper import CONFIG
from job_scraper_integration import JobScraperIntegration

def main():
    print("=== Job Scraping Development Script ===")
    print(f"Started at: {datetime.now()}")
    config = CONFIG
    try:
        # Initialize the scraper
        print("1. Initializing JobScraperIntegration...")
        scraper = JobScraperIntegration()
        print("✓ Successfully initialized scraper")
        # Check current database statistics
        print("\n2. Checking current database statistics...")
        stats = scraper.get_job_statistics()
        print(f"Current job statistics: {stats}")
        print(f"\n3. Testing job scraping with:")
        print(f"   Search terms: {config['SEARCH_TERMS']}")
        print(f"   Locations: {config['LOCATIONS']}")
        print(f"   Platforms: {config['SITE_NAME']}")
        print(f"   Results per search: {config['RESULTS_WANTED']}")
        # Scrape jobs
        jobs_df = scraper.scrape_jobs_from_platforms(
            search_terms=config["SEARCH_TERMS"],
            locations=config["LOCATIONS"],
            platforms=config["SITE_NAME"],
            results_per_search=config["RESULTS_WANTED"],
            job_type=config["JOB_TYPE"],
            is_remote=config["IS_REMOTE"],
            hours_old=config["HOURS_OLD"],
            country_indeed=config["COUNTRY_INDEED"],
            proxies=config["PROXIES"],
            verbose=config["VERBOSE"],
            description_format=config["DESCRIPTION_FORMAT"],
            easy_apply=config["EASY_APPLY"],
            linkedin_fetch_description=config["LINKEDIN_FETCH_DESCRIPTION"]
        )
        if not jobs_df.empty:
            print(f"✓ Successfully scraped {len(jobs_df)} jobs")
            # Show sample of scraped data
            print(f"\n4. Sample of scraped data:")
            print(f"   Columns: {list(jobs_df.columns)}")
            print(f"   First job title: {jobs_df.iloc[0].get('title', 'N/A') if len(jobs_df) > 0 else 'N/A'}")
            print(f"   First company: {jobs_df.iloc[0].get('company', 'N/A') if len(jobs_df) > 0 else 'N/A'}")
            # Clean and transform data
            print("\n5. Cleaning and transforming data...")
            cleaned_df = scraper.clean_and_transform_job_data(jobs_df)
            print(f"✓ Cleaned data: {len(cleaned_df)} jobs remaining")
            print(cleaned_df.head())
            # Save to MongoDB
            print("\n6. Saving to MongoDB...")
            saved_count = scraper.save_jobs_to_mongodb(cleaned_df)
            print(f"✓ Successfully saved {saved_count} jobs to MongoDB")
            # Get updated statistics
            print("\n7. Updated database statistics:")
            updated_stats = scraper.get_job_statistics()
            print(f"Updated stats: {updated_stats}")
            # Show sample of pending jobs
            print("\n8. Sample of pending jobs:")
            pending_jobs = scraper.get_pending_jobs(limit=3)
            for i, job in enumerate(pending_jobs):
                print(f"   Job {i+1}: {job.get('job_title', 'N/A')} at {job.get('company_name', 'N/A')}")
            print("\n=== Script completed successfully! ===")
        else:
            print("✗ No jobs were scraped. This might be due to:")
            print("  - Network connectivity issues")
            print("  - Rate limiting from job sites")
            print("  - No jobs matching the criteria")
            print("  - Jobspy library issues")
    except ImportError as e:
        print(f"✗ Import error: {e}")
        print("Please install the required library:")
        print("pip install python-jobspy")
    except Exception as e:
        print(f"✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 