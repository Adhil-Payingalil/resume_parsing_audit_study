import os
import json
import csv
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Get the script directory and set up paths
script_dir = Path(__file__).parent
data_dir = script_dir / 'data'
logs_dir = Path('logs')

# Create directories if they don't exist
data_dir.mkdir(exist_ok=True)
logs_dir.mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(logs_dir / 'analyze_jd_lengths.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "Resume_study")
MONGODB_COLLECTION = "Job_postings_greenhouse"

class JobDescriptionLengthAnalyzer:
    def __init__(self):
        self.mongo_client = None
        self.collection = None
        self.setup_mongodb_connection()
        
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
        except ConnectionFailure as e:
            raise Exception(f"Failed to connect to MongoDB: {e}")
        except Exception as e:
            raise Exception(f"MongoDB setup error: {e}")
    
    def count_words(self, text: str) -> int:
        """Count words in text, handling None and empty strings"""
        if not text or not isinstance(text, str):
            return 0
        
        # Remove HTML tags if present
        clean_text = re.sub(r'<[^>]+>', '', text)
        # Split by whitespace and filter out empty strings
        words = [word for word in clean_text.split() if word.strip()]
        return len(words)
    
    def count_characters(self, text: str) -> int:
        """Count characters in text, handling None and empty strings"""
        if not text or not isinstance(text, str):
            return 0
        
        # Remove HTML tags if present
        clean_text = re.sub(r'<[^>]+>', '', text)
        # Remove extra whitespace and count characters
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        return len(clean_text)
    
    def analyze_job_descriptions(self) -> Dict:
        """Analyze all job descriptions and return statistics"""
        logger.info("Starting job description length analysis...")
        
        # Get all jobs with job_description field
        jobs_with_descriptions = list(self.collection.find({
            "job_description": {"$exists": True, "$ne": None, "$ne": ""}
        }))
        
        # Get all jobs without job_description field
        jobs_without_descriptions = self.collection.count_documents({
            "$or": [
                {"job_description": {"$exists": False}},
                {"job_description": None},
                {"job_description": ""}
            ]
        })
        
        total_jobs = self.collection.count_documents({})
        
        logger.info(f"Found {len(jobs_with_descriptions)} jobs with descriptions")
        logger.info(f"Found {jobs_without_descriptions} jobs without descriptions")
        logger.info(f"Total jobs in collection: {total_jobs}")
        
        # Analyze lengths
        length_data = []
        word_counts = []
        char_counts = []
        
        # Define thresholds for analysis
        VERY_SHORT_WORDS = 50
        SHORT_WORDS = 100
        MEDIUM_WORDS = 300
        VERY_SHORT_CHARS = 200
        SHORT_CHARS = 500
        MEDIUM_CHARS = 1500
        
        categories = {
            'very_short_words': 0,  # < 50 words
            'short_words': 0,       # 50-99 words
            'medium_words': 0,      # 100-299 words
            'long_words': 0,        # 300+ words
            'very_short_chars': 0,  # < 200 chars
            'short_chars': 0,       # 200-499 chars
            'medium_chars': 0,      # 500-1499 chars
            'long_chars': 0         # 1500+ chars
        }
        
        for job in jobs_with_descriptions:
            job_id = str(job['_id'])
            job_description = job.get('job_description', '')
            
            word_count = self.count_words(job_description)
            char_count = self.count_characters(job_description)
            
            word_counts.append(word_count)
            char_counts.append(char_count)
            
            # Categorize by word count
            if word_count < VERY_SHORT_WORDS:
                categories['very_short_words'] += 1
            elif word_count < SHORT_WORDS:
                categories['short_words'] += 1
            elif word_count < MEDIUM_WORDS:
                categories['medium_words'] += 1
            else:
                categories['long_words'] += 1
            
            # Categorize by character count
            if char_count < VERY_SHORT_CHARS:
                categories['very_short_chars'] += 1
            elif char_count < SHORT_CHARS:
                categories['short_chars'] += 1
            elif char_count < MEDIUM_CHARS:
                categories['medium_chars'] += 1
            else:
                categories['long_chars'] += 1
            
            length_data.append({
                'job_id': job_id,
                'title': job.get('title', 'N/A'),
                'company': job.get('company', 'N/A'),
                'word_count': word_count,
                'char_count': char_count,
                'jd_extraction': job.get('jd_extraction', False),
                'job_link': job.get('job_link', 'N/A')
            })
        
        # Calculate statistics
        if word_counts:
            word_stats = {
                'min': min(word_counts),
                'max': max(word_counts),
                'avg': sum(word_counts) / len(word_counts),
                'median': sorted(word_counts)[len(word_counts) // 2]
            }
        else:
            word_stats = {'min': 0, 'max': 0, 'avg': 0, 'median': 0}
        
        if char_counts:
            char_stats = {
                'min': min(char_counts),
                'max': max(char_counts),
                'avg': sum(char_counts) / len(char_counts),
                'median': sorted(char_counts)[len(char_counts) // 2]
            }
        else:
            char_stats = {'min': 0, 'max': 0, 'avg': 0, 'median': 0}
        
        return {
            'total_jobs': total_jobs,
            'jobs_with_descriptions': len(jobs_with_descriptions),
            'jobs_without_descriptions': jobs_without_descriptions,
            'length_data': length_data,
            'categories': categories,
            'word_stats': word_stats,
            'char_stats': char_stats,
            'thresholds': {
                'very_short_words': VERY_SHORT_WORDS,
                'short_words': SHORT_WORDS,
                'medium_words': MEDIUM_WORDS,
                'very_short_chars': VERY_SHORT_CHARS,
                'short_chars': SHORT_CHARS,
                'medium_chars': MEDIUM_CHARS
            }
        }
    
    def add_length_fields_to_collection(self, length_data: List[Dict]):
        """Add word_count and char_count fields to the MongoDB collection"""
        logger.info("Adding length fields to MongoDB collection...")
        
        updated_count = 0
        error_count = 0
        
        for job_data in length_data:
            try:
                from bson import ObjectId
                
                result = self.collection.update_one(
                    {'_id': ObjectId(job_data['job_id'])},
                    {'$set': {
                        'jd_word_count': job_data['word_count'],
                        'jd_char_count': job_data['char_count'],
                        'jd_length_analyzed_at': datetime.now()
                    }}
                )
                
                if result.modified_count > 0:
                    updated_count += 1
                    if updated_count % 100 == 0:
                        logger.info(f"Updated {updated_count} jobs so far...")
                        
            except Exception as e:
                error_count += 1
                logger.error(f"Error updating job {job_data['job_id']}: {e}")
                continue
        
        logger.info(f"✅ Updated {updated_count} jobs with length data")
        if error_count > 0:
            logger.warning(f"⚠️ {error_count} jobs failed to update")
        
        return updated_count, error_count
    
    def save_analysis_results(self, analysis_results: Dict, filename_suffix: str = ""):
        """Save analysis results to CSV and JSON files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save detailed job data to CSV in data directory
        csv_filename = f"jd_length_analysis{filename_suffix}_{timestamp}.csv"
        csv_path = data_dir / csv_filename
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['job_id', 'title', 'company', 'word_count', 'char_count', 
                         'jd_extraction', 'job_link']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(analysis_results['length_data'])
        
        logger.info(f"✅ Saved detailed job data to {csv_path}")
        
        # Save summary statistics to JSON in data directory
        json_filename = f"jd_analysis_summary{filename_suffix}_{timestamp}.json"
        json_path = data_dir / json_filename
        
        summary = {
            'analysis_timestamp': timestamp,
            'total_jobs': analysis_results['total_jobs'],
            'jobs_with_descriptions': analysis_results['jobs_with_descriptions'],
            'jobs_without_descriptions': analysis_results['jobs_without_descriptions'],
            'categories': analysis_results['categories'],
            'word_statistics': analysis_results['word_stats'],
            'character_statistics': analysis_results['char_stats'],
            'thresholds': analysis_results['thresholds']
        }
        
        with open(json_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(summary, jsonfile, indent=2, default=str)
        
        logger.info(f"✅ Saved summary statistics to {json_path}")
        
        return csv_path, json_path
    
    def identify_low_quality_descriptions(self, analysis_results: Dict, 
                                        word_threshold: int = 50, 
                                        char_threshold: int = 200) -> List[Dict]:
        """Identify job descriptions that are likely low quality based on length"""
        
        low_quality_jobs = []
        
        for job_data in analysis_results['length_data']:
            is_low_quality = (
                job_data['word_count'] < word_threshold or 
                job_data['char_count'] < char_threshold
            )
            
            if is_low_quality:
                low_quality_jobs.append({
                    **job_data,
                    'reason': f"Words: {job_data['word_count']} < {word_threshold} OR Chars: {job_data['char_count']} < {char_threshold}"
                })
        
        logger.info(f"Identified {len(low_quality_jobs)} low quality job descriptions")
        
        # Save low quality jobs to separate CSV in data directory
        if low_quality_jobs:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            low_quality_csv = data_dir / f"low_quality_jobs_{timestamp}.csv"
            
            with open(low_quality_csv, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['job_id', 'title', 'company', 'word_count', 'char_count', 
                             'jd_extraction', 'job_link', 'reason']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(low_quality_jobs)
            
            logger.info(f"✅ Saved low quality jobs to {low_quality_csv}")
        
        return low_quality_jobs
    
    def print_analysis_summary(self, analysis_results: Dict):
        """Print a formatted summary of the analysis"""
        print("\n" + "="*80)
        print("JOB DESCRIPTION LENGTH ANALYSIS SUMMARY")
        print("="*80)
        
        print(f"\n📊 OVERALL STATISTICS:")
        print(f"   Total jobs in collection: {analysis_results['total_jobs']:,}")
        print(f"   Jobs with descriptions: {analysis_results['jobs_with_descriptions']:,}")
        print(f"   Jobs without descriptions: {analysis_results['jobs_without_descriptions']:,}")
        print(f"   Coverage: {(analysis_results['jobs_with_descriptions']/analysis_results['total_jobs']*100):.1f}%")
        
        print(f"\n📝 WORD COUNT STATISTICS:")
        ws = analysis_results['word_stats']
        print(f"   Average: {ws['avg']:.1f} words")
        print(f"   Median: {ws['median']} words")
        print(f"   Range: {ws['min']} - {ws['max']} words")
        
        print(f"\n🔤 CHARACTER COUNT STATISTICS:")
        cs = analysis_results['char_stats']
        print(f"   Average: {cs['avg']:.1f} characters")
        print(f"   Median: {cs['median']} characters")
        print(f"   Range: {cs['min']} - {cs['max']} characters")
        
        print(f"\n📏 LENGTH CATEGORIES:")
        cat = analysis_results['categories']
        thresh = analysis_results['thresholds']
        
        print(f"   BY WORD COUNT:")
        print(f"     Very Short (< {thresh['very_short_words']} words): {cat['very_short_words']:,} jobs")
        print(f"     Short ({thresh['very_short_words']}-{thresh['short_words']-1} words): {cat['short_words']:,} jobs")
        print(f"     Medium ({thresh['short_words']}-{thresh['medium_words']-1} words): {cat['medium_words']:,} jobs")
        print(f"     Long ({thresh['medium_words']}+ words): {cat['long_words']:,} jobs")
        
        print(f"   BY CHARACTER COUNT:")
        print(f"     Very Short (< {thresh['very_short_chars']} chars): {cat['very_short_chars']:,} jobs")
        print(f"     Short ({thresh['very_short_chars']}-{thresh['short_chars']-1} chars): {cat['short_chars']:,} jobs")
        print(f"     Medium ({thresh['short_chars']}-{thresh['medium_chars']-1} chars): {cat['medium_chars']:,} jobs")
        print(f"     Long ({thresh['medium_chars']}+ chars): {cat['long_chars']:,} jobs")
        
        # Calculate percentages for concerning categories
        total_with_desc = analysis_results['jobs_with_descriptions']
        if total_with_desc > 0:
            very_short_word_pct = (cat['very_short_words'] / total_with_desc) * 100
            very_short_char_pct = (cat['very_short_chars'] / total_with_desc) * 100
            
            print(f"\n⚠️ QUALITY CONCERNS:")
            print(f"   Very short descriptions (< {thresh['very_short_words']} words): {very_short_word_pct:.1f}%")
            print(f"   Very short descriptions (< {thresh['very_short_chars']} chars): {very_short_char_pct:.1f}%")
        
        print("="*80)
    
    def close_connection(self):
        """Close MongoDB connection"""
        if self.mongo_client:
            self.mongo_client.close()
            logger.info("MongoDB connection closed")

def main():
    """Main execution function"""
    analyzer = None
    
    try:
        # Initialize analyzer
        analyzer = JobDescriptionLengthAnalyzer()
        
        # Run analysis
        logger.info("Starting job description length analysis...")
        analysis_results = analyzer.analyze_job_descriptions()
        
        # Print summary
        analyzer.print_analysis_summary(analysis_results)
        
        # Save results
        csv_path, json_path = analyzer.save_analysis_results(analysis_results)
        
        # Add length fields to MongoDB collection
        print(f"\n🔄 Adding length fields to MongoDB collection...")
        updated_count, error_count = analyzer.add_length_fields_to_collection(analysis_results['length_data'])
        
        # Identify low quality descriptions
        print(f"\n🔍 Identifying low quality descriptions...")
        low_quality_jobs = analyzer.identify_low_quality_descriptions(analysis_results)
        
        print(f"\n✅ ANALYSIS COMPLETE!")
        print(f"   📄 Detailed data saved to: {csv_path}")
        print(f"   📊 Summary saved to: {json_path}")
        print(f"   💾 MongoDB updated: {updated_count} jobs")
        print(f"   ⚠️ Low quality jobs identified: {len(low_quality_jobs)}")
        
        if len(low_quality_jobs) > 0:
            print(f"\n💡 RECOMMENDATION:")
            print(f"   Consider reviewing the {len(low_quality_jobs)} low quality job descriptions")
            print(f"   You may want to set jd_extraction=false for these jobs")
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise
    
    finally:
        if analyzer:
            analyzer.close_connection()

if __name__ == "__main__":
    main()
