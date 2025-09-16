"""
Email Application Analysis using Direct Text Search
==================================================

This script analyzes job postings in MongoDB to identify those that accept
applications via email using direct text search with regex patterns.

The analysis uses:
1. Direct text search with regex patterns to find email application instructions
2. Multiple search patterns to catch different ways of expressing email applications
3. Text analysis to extract relevant information and email addresses
4. MongoDB collection creation to store results
5. CSV output with detailed results

Usage:
------
cd "Adhoc analysis/email_application_analysis"
python email_application_analysis_v2.py

Output:
-------
- Console: Progress updates and summary statistics
- MongoDB Collection: email_application_jobs - All jobs with email applications
- CSV Files in output/ folder:
  * email_application_analysis_results.csv - Detailed results with job info
  * email_analysis_summary.txt - Summary statistics and analysis

Dependencies:
------------
- MongoDB connection (via libs.mongodb)
- Environment variables: MONGODB_URI
"""

import os
import sys
import json
import csv
import re
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from collections import defaultdict, Counter
from dotenv import load_dotenv

# Add the project root to the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from libs.mongodb import _get_mongo_client
from utils import get_logger

# Load environment variables
load_dotenv()

# Initialize logger
logger = get_logger(__name__)

class EmailApplicationAnalyzer:
    """Analyzer for finding job postings that accept applications via email."""
    
    def __init__(self, db_name: str = "Resume_study", 
                 source_collection: str = "job_postings",
                 target_collection: str = "email_application_jobs"):
        """Initialize the analyzer."""
        self.db_name = db_name
        self.source_collection = source_collection
        self.target_collection = target_collection
        self.mongo_client = None
        self.db = None
        self.source_coll = None
        self.target_coll = None
        
        # Email application search patterns (focused on genuine application instructions)
        self.email_patterns = [
            # Direct email application instructions
            {"pattern": r"submit.*resume.*to.*@", "description": "Submit resume to email"},
            {"pattern": r"email.*resume.*to.*@", "description": "Email resume to address"},
            {"pattern": r"send.*resume.*to.*@", "description": "Send resume to email"},
            {"pattern": r"apply.*by.*email.*to.*@", "description": "Apply by email to address"},
            {"pattern": r"email.*application.*to.*@", "description": "Email application to address"},
            
            # Application submission patterns
            {"pattern": r"submit.*application.*to.*@", "description": "Submit application to email"},
            {"pattern": r"send.*application.*to.*@", "description": "Send application to email"},
            {"pattern": r"email.*cover letter.*to.*@", "description": "Email cover letter to address"},
            {"pattern": r"submit.*via email.*to.*@", "description": "Submit via email to address"},
            {"pattern": r"apply.*via email.*to.*@", "description": "Apply via email to address"},
            
            # Direct application instructions with email addresses
            {"pattern": r"to apply.*email.*@", "description": "To apply email instruction"},
            {"pattern": r"how to apply.*email.*@", "description": "How to apply email instruction"},
            {"pattern": r"application.*email.*@", "description": "Application email instruction"},
            {"pattern": r"resume.*email.*@", "description": "Resume email instruction"},
            {"pattern": r"cv.*email.*@", "description": "CV email instruction"},
        ]
        
        # Accommodation email patterns to exclude
        self.accommodation_patterns = [
            r"accommodation",
            r"accessibility",
            r"disability",
            r"reasonable accommodation",
            r"recruiting.*accommodation",
            r"hr.*accommodation",
            r"talent.*accommodation",
            r"recruitment.*accommodation",
            r"careers.*accommodation",
            r"hiring.*accommodation",
            r"employment.*accommodation",
            r"workplace.*accommodation",
            r"process.*accommodation",
            r"request.*accommodation",
            r"need.*accommodation",
            r"require.*accommodation",
            r"assistance.*accommodation",
            r"support.*accommodation",
            r"help.*accommodation",
            r"contact.*accommodation"
        ]
        
        self.results = []
        self.unique_job_ids = set()
        
        logger.info("EmailApplicationAnalyzer initialized")
    
    def connect_to_mongodb(self):
        """Connect to MongoDB."""
        try:
            self.mongo_client = _get_mongo_client()
            if not self.mongo_client:
                raise ConnectionError("Failed to connect to MongoDB")
            
            self.db = self.mongo_client[self.db_name]
            self.source_coll = self.db[self.source_collection]
            self.target_coll = self.db[self.target_collection]
            
            logger.info(f"Connected to MongoDB: {self.db_name}")
            logger.info(f"Source collection: {self.source_collection}")
            logger.info(f"Target collection: {self.target_collection}")
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    def search_for_email_applications(self):
        """Search for jobs with email applications using direct text search with filtering."""
        logger.info("Starting email application search with accommodation filtering...")
        
        total_jobs = self.source_coll.count_documents({})
        logger.info(f"Total jobs in source collection: {total_jobs:,}")
        
        all_matches = set()
        pattern_results = {}
        accommodation_filtered = 0
        
        for i, pattern_info in enumerate(self.email_patterns, 1):
            pattern = pattern_info["pattern"]
            description = pattern_info["description"]
            
            logger.info(f"Searching pattern {i}/{len(self.email_patterns)}: {description}")
            
            # Create MongoDB regex query
            query = {"description": {"$regex": pattern, "$options": "i"}}
            
            # Find matches
            matches = list(self.source_coll.find(query))
            
            if matches:
                logger.info(f"Found {len(matches)} initial matches for pattern: {description}")
                
                # Filter out accommodation emails
                genuine_matches = []
                for match in matches:
                    description_text = match.get('description', '')
                    if self.is_genuine_application_email(description_text):
                        genuine_matches.append(match)
                    else:
                        accommodation_filtered += 1
                
                if genuine_matches:
                    logger.info(f"Found {len(genuine_matches)} genuine matches (filtered {len(matches) - len(genuine_matches)} accommodation emails)")
                    pattern_results[description] = len(genuine_matches)
                    
                    for match in genuine_matches:
                        job_id = match['_id']
                        all_matches.add(job_id)
                else:
                    logger.info(f"No genuine matches found (all {len(matches)} were accommodation emails)")
                    pattern_results[description] = 0
            else:
                logger.info(f"No matches found for pattern: {description}")
                pattern_results[description] = 0
        
        logger.info(f"Total unique jobs with genuine email applications: {len(all_matches)}")
        logger.info(f"Total accommodation emails filtered out: {accommodation_filtered}")
        
        # Store pattern results for summary
        self.pattern_results = pattern_results
        self.unique_job_ids = all_matches
        self.accommodation_filtered = accommodation_filtered
        
        return all_matches
    
    def extract_email_addresses(self, text: str) -> List[str]:
        """Extract email addresses from text."""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        return re.findall(email_pattern, text)
    
    def is_accommodation_email(self, text: str) -> bool:
        """Check if the text contains accommodation-related content."""
        text_lower = text.lower()
        for pattern in self.accommodation_patterns:
            if re.search(pattern, text_lower):
                return True
        return False
    
    def is_genuine_application_email(self, text: str) -> bool:
        """Check if the text contains genuine application email instructions."""
        text_lower = text.lower()
        
        # Must contain an email address
        if not re.search(r'@.*\.(com|ca|org|net)', text_lower):
            return False
        
        # Must contain application-related keywords
        application_keywords = [
            'apply', 'application', 'resume', 'cv', 'cover letter', 
            'submit', 'send', 'email', 'candidate', 'position', 'job'
        ]
        
        if not any(keyword in text_lower for keyword in application_keywords):
            return False
        
        # Must NOT be accommodation-related
        if self.is_accommodation_email(text):
            return False
        
        # Must contain direct application instruction patterns
        application_patterns = [
            r'submit.*resume.*to',
            r'email.*resume.*to',
            r'send.*resume.*to',
            r'apply.*by.*email',
            r'email.*application.*to',
            r'submit.*application.*to',
            r'send.*application.*to',
            r'email.*cover letter.*to',
            r'to apply.*email',
            r'how to apply.*email',
            r'application.*email',
            r'resume.*email',
            r'cv.*email'
        ]
        
        for pattern in application_patterns:
            if re.search(pattern, text_lower):
                return True
        
        return False
    
    def extract_relevant_text(self, description: str, max_lines: int = 5) -> List[str]:
        """Extract relevant lines from job description that contain email/application keywords."""
        keywords = ['email', 'apply', 'submit', 'resume', '@', 'contact', 'send']
        lines = description.split('\n')
        relevant_lines = []
        
        for line in lines:
            line = line.strip()
            if line and any(keyword in line.lower() for keyword in keywords):
                relevant_lines.append(line)
                if len(relevant_lines) >= max_lines:
                    break
        
        return relevant_lines
    
    def collect_detailed_results(self):
        """Collect detailed information for all unique jobs."""
        logger.info("Collecting detailed results...")
        
        for job_id in self.unique_job_ids:
            job_data = self.source_coll.find_one({"_id": job_id})
            
            if not job_data:
                continue
            
            # Extract email addresses from description
            description = job_data.get('description', '')
            email_addresses = self.extract_email_addresses(description)
            
            # Extract relevant text
            relevant_text = self.extract_relevant_text(description)
            
            # Create result record
            result = {
                'job_id': str(job_id),
                'job_title': job_data.get('title', 'N/A'),
                'company_name': job_data.get('company', 'N/A'),
                'source_platform': job_data.get('site', 'N/A'),
                'search_term': job_data.get('search_term', 'N/A'),
                'location': job_data.get('location', 'Not specified'),
                'job_url': job_data.get('job_url', 'N/A'),
                'scraped_at': job_data.get('scraped_at', 'N/A'),
                'email_addresses': email_addresses,
                'num_email_addresses': len(email_addresses),
                'relevant_text': ' | '.join(relevant_text[:3]),  # First 3 relevant lines
                'description_length': len(description),
                'analysis_date': datetime.now().isoformat()
            }
            
            # Add job description if requested
            result['job_description'] = description[:1000] + "..." if len(description) > 1000 else description
            
            self.results.append(result)
        
        logger.info(f"Collected {len(self.results)} detailed results")
    
    def save_to_mongodb(self):
        """Save all results to the target MongoDB collection."""
        logger.info(f"Saving results to MongoDB collection: {self.target_collection}")
        
        if not self.results:
            logger.warning("No results to save")
            return
        
        # Clear existing collection
        self.target_coll.delete_many({})
        logger.info("Cleared existing collection")
        
        # Insert new results
        self.target_coll.insert_many(self.results)
        logger.info(f"Saved {len(self.results)} jobs to {self.target_collection} collection")
        
        # Create index on job_id for faster lookups
        self.target_coll.create_index("job_id")
        self.target_coll.create_index("company_name")
        self.target_coll.create_index("source_platform")
        logger.info("Created indexes on job_id, company_name, and source_platform")
    
    def save_to_csv(self):
        """Save results to CSV file."""
        if not self.results:
            logger.warning("No results to save to CSV")
            return
        
        # Create output directory
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        
        # Save detailed results
        csv_file = os.path.join(output_dir, "email_application_analysis_results.csv")
        
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            if self.results:
                writer = csv.DictWriter(f, fieldnames=self.results[0].keys())
                writer.writeheader()
                writer.writerows(self.results)
        
        logger.info(f"Saved detailed results to {csv_file}")
    
    def generate_summary(self, total_jobs: int) -> Dict[str, Any]:
        """Generate analysis summary."""
        unique_matches = len(self.unique_job_ids)
        percentage = (unique_matches / total_jobs * 100) if total_jobs > 0 else 0
        
        # Platform distribution
        platform_stats = Counter()
        search_term_stats = Counter()
        email_count_stats = Counter()
        
        for result in self.results:
            platform_stats[result['source_platform']] += 1
            search_term_stats[result['search_term']] += 1
            email_count_stats[result['num_email_addresses']] += 1
        
        summary = {
            'analysis_date': datetime.now().isoformat(),
            'total_jobs_analyzed': total_jobs,
            'jobs_with_email_applications': unique_matches,
            'percentage': round(percentage, 2),
            'accommodation_emails_filtered': getattr(self, 'accommodation_filtered', 0),
            'pattern_results': self.pattern_results,
            'platform_distribution': dict(platform_stats.most_common(10)),
            'top_search_terms': dict(search_term_stats.most_common(10)),
            'email_count_distribution': dict(email_count_stats),
            'total_email_addresses_found': sum(result['num_email_addresses'] for result in self.results)
        }
        
        return summary
    
    def save_summary(self, summary: Dict[str, Any]):
        """Save summary to text file."""
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        
        summary_file = os.path.join(output_dir, "email_analysis_summary.txt")
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("EMAIL APPLICATION ANALYSIS RESULTS\n")
            f.write("=" * 60 + "\n")
            f.write(f"Analysis Date: {summary['analysis_date']}\n")
            f.write(f"Total Jobs Analyzed: {summary['total_jobs_analyzed']:,}\n")
            f.write(f"Jobs with Email Applications: {summary['jobs_with_email_applications']}\n")
            f.write(f"Percentage: {summary['percentage']}%\n")
            f.write(f"Accommodation Emails Filtered: {summary['accommodation_emails_filtered']}\n")
            f.write(f"Total Email Addresses Found: {summary['total_email_addresses_found']}\n\n")
            
            f.write("PATTERN RESULTS:\n")
            for pattern, count in summary['pattern_results'].items():
                f.write(f"  {pattern}: {count} matches\n")
            
            f.write("\nPLATFORM DISTRIBUTION:\n")
            for platform, count in summary['platform_distribution'].items():
                f.write(f"  {platform}: {count}\n")
            
            f.write("\nTOP SEARCH TERMS:\n")
            for term, count in summary['top_search_terms'].items():
                f.write(f"  {term}: {count}\n")
            
            f.write("\nEMAIL COUNT DISTRIBUTION:\n")
            for count, jobs in summary['email_count_distribution'].items():
                f.write(f"  {count} email(s): {jobs} jobs\n")
            
            f.write("=" * 60 + "\n")
        
        logger.info(f"Saved summary to {summary_file}")
    
    def run_analysis(self):
        """Run the complete email application analysis."""
        try:
            logger.info("Starting Email Application Analysis")
            
            # Connect to MongoDB
            self.connect_to_mongodb()
            
            # Search for email applications
            unique_jobs = self.search_for_email_applications()
            
            if not unique_jobs:
                logger.warning("No jobs with email applications found")
                return
            
            # Collect detailed results
            self.collect_detailed_results()
            
            # Save to MongoDB
            self.save_to_mongodb()
            
            # Save to CSV
            self.save_to_csv()
            
            # Generate and save summary
            total_jobs = self.source_coll.count_documents({})
            summary = self.generate_summary(total_jobs)
            self.save_summary(summary)
            
            # Print summary to console
            print("\n" + "=" * 60)
            print("EMAIL APPLICATION ANALYSIS RESULTS")
            print("=" * 60)
            print(f"Analysis Date: {summary['analysis_date']}")
            print(f"Total Jobs Analyzed: {summary['total_jobs_analyzed']:,}")
            print(f"Jobs with Email Applications: {summary['jobs_with_email_applications']}")
            print(f"Percentage: {summary['percentage']}%")
            print(f"Accommodation Emails Filtered: {summary['accommodation_emails_filtered']}")
            print(f"Total Email Addresses Found: {summary['total_email_addresses_found']}")
            print(f"MongoDB Collection Created: {self.target_collection}")
            print("=" * 60)
            
            logger.info("Email Application Analysis completed successfully")
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            raise

def main():
    """Main function."""
    try:
        analyzer = EmailApplicationAnalyzer()
        analyzer.run_analysis()
    except Exception as e:
        logger.error(f"Failed to run analysis: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
