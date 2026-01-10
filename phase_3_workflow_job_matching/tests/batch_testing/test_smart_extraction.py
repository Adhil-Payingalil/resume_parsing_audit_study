"""
Smart Extraction Test Script

This script tests the smart content extraction from greenhouse job descriptions
and shows you the original content vs. the extracted content that gets embedded.

Usage:
    python test_smart_extraction.py
"""

import os
import sys
from typing import List, Dict, Any

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from libs.mongodb import _get_mongo_client
from utils import get_logger

logger = get_logger(__name__)

class SmartExtractionTester:
    """
    Tests and demonstrates the smart content extraction from job descriptions.
    """
    
    def __init__(self, db_name: str = "Resume_study"):
        self.db_name = db_name
        self.mongo_client = _get_mongo_client()
        if not self.mongo_client:
            raise ConnectionError("Failed to connect to MongoDB")
        
        self.db = self.mongo_client[db_name]
        self.job_collection = self.db["Job_postings_greenhouse"]
        
        logger.info(f"SmartExtractionTester initialized for database: {db_name}")
    
    def extract_greenhouse_job_content(self, job_doc: Dict[str, Any]) -> str:
        """
        Extract content from greenhouse job document for embedding (same logic as main script).
        
        Args:
            job_doc (Dict[str, Any]): Job document from MongoDB
            
        Returns:
            str: Extracted content for embedding
        """
        try:
            content_parts = []
            
            # Extract job title
            job_title = job_doc.get("title", "")
            if job_title:
                content_parts.append(f"Job Title: {job_title}")
            
            # Extract job description (main content)
            job_description = job_doc.get("job_description", "")
            if job_description:
                # Focus on key sections for better embeddings
                lines = job_description.split('\n')
                key_sections = []
                
                for line in lines:
                    line_lower = line.lower().strip()
                    # Look for sections that typically contain requirements and skills
                    if any(keyword in line_lower for keyword in [
                        'requirements', 'qualifications', 'skills', 'responsibilities',
                        'duties', 'experience', 'education', 'must have', 'should have',
                        'preferred', 'knowledge of', 'proficiency in', 'familiarity with',
                        'what you\'ll do', 'what we\'re looking for', 'nice to have'
                    ]):
                        key_sections.append(line.strip())
                
                # If we found key sections, use them; otherwise use the full description
                if key_sections:
                    content_parts.extend(key_sections)
                else:
                    # Use first 3000 characters of description
                    content_parts.append(job_description[:3000])
            
            # Join all parts
            extracted_content = " ".join(content_parts)
            
            # Limit to reasonable length for embedding (max 8000 characters)
            if len(extracted_content) > 8000:
                extracted_content = extracted_content[:8000]
                logger.info(f"Truncated job content from {len(' '.join(content_parts))} to 8000 characters")
            
            return extracted_content
            
        except Exception as e:
            logger.error(f"Error extracting greenhouse job content: {e}")
            return ""
    
    def get_sample_jobs(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get sample job documents for testing.
        
        Args:
            limit (int): Number of sample jobs to retrieve
            
        Returns:
            List[Dict[str, Any]]: List of sample job documents
        """
        try:
            # Get jobs with jd_extraction=True
            jobs = list(self.job_collection.find({
                "jd_extraction": True
            }).limit(limit))
            
            logger.info(f"Retrieved {len(jobs)} sample jobs")
            return jobs
            
        except Exception as e:
            logger.error(f"Error retrieving sample jobs: {e}")
            return []
    
    def test_extraction(self, job_doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Test extraction for a single job document.
        
        Args:
            job_doc (Dict[str, Any]): Job document to test
            
        Returns:
            Dict[str, Any]: Test results
        """
        job_title = job_doc.get("title", "Unknown")
        job_description = job_doc.get("job_description", "")
        
        # Extract content using the same logic as the main script
        extracted_content = self.extract_greenhouse_job_content(job_doc)
        
        # Analyze the extraction
        original_length = len(job_description)
        extracted_length = len(extracted_content)
        compression_ratio = (extracted_length / original_length * 100) if original_length > 0 else 0
        
        # Count key sections found
        key_sections = []
        if job_description:
            lines = job_description.split('\n')
            for line in lines:
                line_lower = line.lower().strip()
                if any(keyword in line_lower for keyword in [
                    'requirements', 'qualifications', 'skills', 'responsibilities',
                    'duties', 'experience', 'education', 'must have', 'should have',
                    'preferred', 'knowledge of', 'proficiency in', 'familiarity with',
                    'what you\'ll do', 'what we\'re looking for', 'nice to have'
                ]):
                    key_sections.append(line.strip())
        
        return {
            "job_title": job_title,
            "original_description": job_description,
            "extracted_content": extracted_content,
            "original_length": original_length,
            "extracted_length": extracted_length,
            "compression_ratio": compression_ratio,
            "key_sections_found": len(key_sections),
            "key_sections": key_sections,
            "used_smart_extraction": len(key_sections) > 0
        }
    
    def run_tests(self, num_samples: int = 5):
        """
        Run extraction tests on sample jobs.
        
        Args:
            num_samples (int): Number of sample jobs to test
        """
        try:
            logger.info(f"Running smart extraction tests on {num_samples} sample jobs")
            
            # Get sample jobs
            sample_jobs = self.get_sample_jobs(num_samples)
            
            if not sample_jobs:
                logger.error("No sample jobs available for testing")
                return
            
            print("\n" + "="*80)
            print("SMART EXTRACTION TEST RESULTS")
            print("="*80)
            
            for i, job in enumerate(sample_jobs, 1):
                print(f"\n{'='*20} JOB {i} {'='*20}")
                
                # Test extraction
                result = self.test_extraction(job)
                
                print(f"Job Title: {result['job_title']}")
                print(f"Original Length: {result['original_length']} characters")
                print(f"Extracted Length: {result['extracted_length']} characters")
                print(f"Compression Ratio: {result['compression_ratio']:.1f}%")
                print(f"Key Sections Found: {result['key_sections_found']}")
                print(f"Used Smart Extraction: {result['used_smart_extraction']}")
                
                print(f"\n--- ORIGINAL JOB DESCRIPTION ---")
                print(result['original_description'][:500] + "..." if len(result['original_description']) > 500 else result['original_description'])
                
                print(f"\n--- EXTRACTED CONTENT FOR EMBEDDING ---")
                print(result['extracted_content'])
                
                if result['key_sections']:
                    print(f"\n--- KEY SECTIONS IDENTIFIED ---")
                    for section in result['key_sections'][:5]:  # Show first 5 key sections
                        print(f"• {section}")
                    if len(result['key_sections']) > 5:
                        print(f"... and {len(result['key_sections']) - 5} more sections")
                
                print(f"\n{'='*60}")
            
            # Summary statistics
            print(f"\n{'='*20} SUMMARY STATISTICS {'='*20}")
            total_original = sum(self.test_extraction(job)['original_length'] for job in sample_jobs)
            total_extracted = sum(self.test_extraction(job)['extracted_length'] for job in sample_jobs)
            avg_compression = (total_extracted / total_original * 100) if total_original > 0 else 0
            smart_extractions = sum(1 for job in sample_jobs if self.test_extraction(job)['used_smart_extraction'])
            
            print(f"Total Jobs Tested: {len(sample_jobs)}")
            print(f"Average Compression Ratio: {avg_compression:.1f}%")
            print(f"Jobs Using Smart Extraction: {smart_extractions}/{len(sample_jobs)}")
            print(f"Smart Extraction Success Rate: {smart_extractions/len(sample_jobs)*100:.1f}%")
            print("="*80)
            
        except Exception as e:
            logger.error(f"Error running extraction tests: {e}")

def main():
    """Main function to run smart extraction tests."""
    try:
        logger.info("Starting smart extraction tests")
        
        # Initialize tester
        tester = SmartExtractionTester()
        
        # Run tests
        tester.run_tests(num_samples=5)
        
        logger.info("Smart extraction tests completed")
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise

if __name__ == "__main__":
    main()
