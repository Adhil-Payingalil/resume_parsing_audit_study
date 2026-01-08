"""
Email Application Analysis using Vector Search
============================================

This script analyzes job postings in MongoDB to identify those that accept
applications via email using vector search with pre-trained queries.

The analysis uses:
1. Vector search to find job descriptions similar to email application phrases
2. Similarity scoring to rank potential matches
3. Text analysis to extract relevant information
4. CSV output with detailed results

Usage:
------
cd "Adhoc analysis/email_application_analysis"
python email_application_analysis.py

Output:
-------
- Console: Progress updates and summary statistics
- CSV Files in output/ folder:
  * email_application_analysis_results.csv - Detailed results with job info
  * email_analysis_summary.txt - Summary statistics and analysis

Dependencies:
------------
- MongoDB connection (via libs.mongodb)
- Environment variables (.env file in root)
- Google Generative AI for embedding generation
- Python standard libraries: os, sys, json, csv, time
"""

import os
import sys
import json
import csv
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict, Counter
from google import genai
from dotenv import load_dotenv

# Add the project root to the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from libs.mongodb import _get_mongo_client
from utils import get_logger
from config_email_analysis import EmailAnalysisConfig, default_config

# Load environment variables
load_dotenv()

# Setup logging
logger = get_logger(__name__)

class EmailApplicationAnalyzer:
    """Analyzes job postings to identify those accepting email applications."""
    
    def __init__(self, config: EmailAnalysisConfig = None):
        """Initialize the analyzer with configuration."""
        self.config = config or default_config
        
        # Get MongoDB client
        self.mongo_client = _get_mongo_client()
        if not self.mongo_client:
            raise ConnectionError("Failed to connect to MongoDB")
        
        self.db = self.mongo_client[self.config.db_name]
        self.collection = self.db[self.config.collection_name]
        
        # Setup Google AI for embedding generation
        self._setup_google_ai()
        
        # Create output directory
        self.output_dir = os.path.join(os.path.dirname(__file__), self.config.output_folder)
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Results storage
        self.results = []
        self.query_stats = defaultdict(int)
        self.job_stats = defaultdict(int)
        
        logger.info(f"EmailApplicationAnalyzer initialized")
        logger.info(f"Database: {self.config.db_name}.{self.config.collection_name}")
        logger.info(f"Vector search index: {self.config.vector_search_index}")
        logger.info(f"Similarity threshold: {self.config.similarity_threshold}")
    
    def _setup_google_ai(self):
        """Setup Google AI for embedding generation."""
        try:
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                raise ValueError("GEMINI_API_KEY not found in environment variables")
            
            self.client = genai.Client(api_key=api_key)
            logger.info("Google AI setup successful")
        except Exception as e:
            logger.error(f"Failed to setup Google AI: {e}")
            raise
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using Google AI."""
        try:
            response = self.client.models.embed_content(
                model="models/embedding-001",
                contents=text
            )
            embedding = response.embeddings[0].values
            return embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise
    
    def get_job_count(self) -> int:
        """Get total number of jobs in collection."""
        try:
            total_jobs = self.collection.count_documents({})
            logger.info(f"Total jobs in collection: {total_jobs}")
            return total_jobs
        except Exception as e:
            logger.error(f"Failed to get job count: {e}")
            return 0
    
    def analyze_email_applications(self) -> Dict[str, Any]:
        """Main analysis function using vector search."""
        logger.info("Starting email application analysis...")
        
        # Get total job count
        total_jobs = self.get_job_count()
        if total_jobs == 0:
            logger.error("No jobs found in collection")
            return {"error": "No jobs found"}
        
        # Generate embeddings for email application queries
        logger.info("Generating embeddings for email application queries...")
        query_embeddings = {}
        
        for i, query in enumerate(self.config.email_application_queries):
            try:
                logger.info(f"Generating embedding for query {i+1}/{len(self.config.email_application_queries)}: '{query}'")
                embedding = self.generate_embedding(query)
                query_embeddings[query] = embedding
                time.sleep(0.1)  # Small delay to avoid rate limiting
            except Exception as e:
                logger.error(f"Failed to generate embedding for query '{query}': {e}")
                continue
        
        if not query_embeddings:
            logger.error("No query embeddings generated")
            return {"error": "Failed to generate query embeddings"}
        
        logger.info(f"Generated {len(query_embeddings)} query embeddings")
        
        # Perform vector search for each query
        all_matches = set()  # Use set to avoid duplicates
        query_results = {}
        
        for query, embedding in query_embeddings.items():
            logger.info(f"Searching for jobs similar to: '{query}'")
            
            try:
                # MongoDB vector search
                pipeline = [
                    {
                        "$vectorSearch": {
                            "index": self.config.vector_search_index,
                            "path": "jd_embedding",
                            "queryVector": embedding,
                            "numCandidates": self.config.max_results_per_query * 2,
                            "limit": self.config.max_results_per_query
                        }
                    },
                    {
                        "$addFields": {
                            "similarity_score": {"$meta": "vectorSearchScore"}
                        }
                    },
                    {
                        "$match": {
                            "similarity_score": {"$gte": self.config.similarity_threshold}
                        }
                    }
                ]
                
                cursor = self.collection.aggregate(pipeline)
                matches = list(cursor)
                
                logger.info(f"Found {len(matches)} matches for query: '{query}'")
                self.query_stats[query] = len(matches)
                
                query_results[query] = matches
                
                # Add to all_matches set
                for match in matches:
                    all_matches.add(match['_id'])
                
            except Exception as e:
                logger.error(f"Vector search failed for query '{query}': {e}")
                continue
        
        logger.info(f"Total unique jobs found across all queries: {len(all_matches)}")
        
        # Collect detailed results
        self._collect_detailed_results(query_results)
        
        # Generate summary
        summary = self._generate_summary(total_jobs, len(all_matches))
        
        return {
            "summary": summary,
            "results": self.results,
            "query_stats": dict(self.query_stats),
            "total_jobs_analyzed": total_jobs,
            "jobs_with_email_applications": len(all_matches)
        }
    
    def _collect_detailed_results(self, query_results: Dict[str, List[Dict]]):
        """Collect detailed results from query matches."""
        logger.info("Collecting detailed results...")
        
        # Create a mapping of job_id to all matching queries
        job_matches = defaultdict(list)
        
        for query, matches in query_results.items():
            for match in matches:
                job_id = match['_id']
                job_matches[job_id].append({
                    'query': query,
                    'similarity_score': match.get('similarity_score', 0),
                    'job_data': match
                })
        
        # Process each job with its matches
        for job_id, matches in job_matches.items():
            # Get the job data (use the first match as they should be identical)
            job_data = matches[0]['job_data']
            
            # Calculate max similarity score
            max_score = max(match['similarity_score'] for match in matches)
            
            # Get matching queries
            matching_queries = [match['query'] for match in matches]
            
            # Extract relevant information
            result = {
                'job_id': str(job_id),
                'job_title': job_data.get('title', 'N/A'),
                'company_name': job_data.get('company', 'N/A'),
                'source_platform': job_data.get('site', 'N/A'),
                'search_term': job_data.get('search_term', 'N/A'),
                'location': self._extract_location(job_data),
                'max_similarity_score': max_score,
                'matching_queries': '; '.join(matching_queries),
                'num_matching_queries': len(matching_queries),
                'scraped_at': job_data.get('scraped_at', 'N/A'),
                'job_url': job_data.get('job_url', 'N/A')
            }
            
            # Add job description if requested
            if self.config.include_job_description:
                result['job_description'] = job_data.get('description', 'N/A')
            
            # Add individual query scores if requested
            if self.config.include_confidence_scores:
                query_scores = {}
                for match in matches:
                    query_scores[match['query']] = match['similarity_score']
                result['query_scores'] = json.dumps(query_scores)
            
            self.results.append(result)
        
        logger.info(f"Collected {len(self.results)} detailed results")
    
    def _extract_location(self, job_data: Dict) -> str:
        """Extract location information from job data."""
        location = job_data.get('location', 'Not specified')
        return location if location else 'Not specified'
    
    def _generate_summary(self, total_jobs: int, unique_matches: int) -> Dict[str, Any]:
        """Generate analysis summary."""
        percentage = (unique_matches / total_jobs * 100) if total_jobs > 0 else 0
        
        # Analyze by source platform
        platform_stats = Counter()
        search_term_stats = Counter()
        
        for result in self.results:
            platform_stats[result['source_platform']] += 1
            search_term_stats[result['search_term']] += 1
        
        return {
            'analysis_timestamp': datetime.now().isoformat(),
            'total_jobs_in_collection': total_jobs,
            'jobs_with_email_applications': unique_matches,
            'percentage_with_email_applications': round(percentage, 2),
            'similarity_threshold_used': self.config.similarity_threshold,
            'num_email_queries_used': len(self.config.email_application_queries),
            'platform_distribution': dict(platform_stats),
            'search_term_distribution': dict(search_term_stats),
            'query_performance': dict(self.query_stats)
        }
    
    def save_results(self, analysis_results: Dict[str, Any]):
        """Save results to CSV and summary files."""
        logger.info("Saving results...")
        
        # Save detailed results to CSV
        csv_path = os.path.join(self.output_dir, self.config.results_filename)
        
        if self.results:
            fieldnames = list(self.results[0].keys())
            
            with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.results)
            
            logger.info(f"Saved {len(self.results)} results to {csv_path}")
        else:
            logger.warning("No results to save")
        
        # Save summary
        summary_path = os.path.join(self.output_dir, self.config.summary_filename)
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write("EMAIL APPLICATION ANALYSIS SUMMARY\n")
            f.write("=" * 50 + "\n\n")
            
            summary = analysis_results['summary']
            
            f.write(f"Analysis Date: {summary['analysis_timestamp']}\n")
            f.write(f"Total Jobs in Collection: {summary['total_jobs_in_collection']:,}\n")
            f.write(f"Jobs with Email Applications: {summary['jobs_with_email_applications']:,}\n")
            f.write(f"Percentage: {summary['percentage_with_email_applications']}%\n\n")
            
            f.write(f"Similarity Threshold: {summary['similarity_threshold_used']}\n")
            f.write(f"Email Queries Used: {summary['num_email_queries_used']}\n\n")
            
            f.write("PLATFORM DISTRIBUTION:\n")
            for platform, count in summary['platform_distribution'].items():
                f.write(f"  {platform}: {count}\n")
            
            f.write("\nSEARCH TERM DISTRIBUTION:\n")
            for term, count in summary['search_term_distribution'].items():
                f.write(f"  {term}: {count}\n")
            
            f.write("\nQUERY PERFORMANCE:\n")
            for query, count in summary['query_performance'].items():
                f.write(f"  '{query}': {count} matches\n")
        
        logger.info(f"Saved summary to {summary_path}")
    
    def print_summary(self, analysis_results: Dict[str, Any]):
        """Print analysis summary to console."""
        summary = analysis_results['summary']
        
        print("\n" + "=" * 60)
        print("EMAIL APPLICATION ANALYSIS RESULTS")
        print("=" * 60)
        print(f"Analysis Date: {summary['analysis_timestamp']}")
        print(f"Total Jobs in Collection: {summary['total_jobs_in_collection']:,}")
        print(f"Jobs with Email Applications: {summary['jobs_with_email_applications']:,}")
        print(f"Percentage: {summary['percentage_with_email_applications']}%")
        print(f"Similarity Threshold: {summary['similarity_threshold_used']}")
        print(f"Email Queries Used: {summary['num_email_queries_used']}")
        
        print("\nPLATFORM DISTRIBUTION:")
        for platform, count in summary['platform_distribution'].items():
            print(f"  {platform}: {count}")
        
        print("\nTOP SEARCH TERMS:")
        sorted_terms = sorted(summary['search_term_distribution'].items(), 
                            key=lambda x: x[1], reverse=True)
        for term, count in sorted_terms[:10]:  # Top 10
            print(f"  {term}: {count}")
        
        print("\nQUERY PERFORMANCE:")
        sorted_queries = sorted(summary['query_performance'].items(), 
                              key=lambda x: x[1], reverse=True)
        for query, count in sorted_queries[:5]:  # Top 5
            print(f"  '{query}': {count} matches")
        
        print("=" * 60)

def main():
    """Main function to run the email application analysis."""
    try:
        logger.info("Starting Email Application Analysis")
        
        # Initialize analyzer
        analyzer = EmailApplicationAnalyzer()
        
        # Run analysis
        results = analyzer.analyze_email_applications()
        
        if "error" in results:
            logger.error(f"Analysis failed: {results['error']}")
            return
        
        # Save results
        analyzer.save_results(results)
        
        # Print summary
        analyzer.print_summary(results)
        
        logger.info("Email Application Analysis completed successfully")
        
    except Exception as e:
        logger.error(f"Analysis failed with error: {e}")
        raise

if __name__ == "__main__":
    main()
